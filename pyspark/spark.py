from typing import List
from emi_sdk.client import StudioClient
from emi_sdk.params import *
from pyspark.sql import SparkSession
import json
import html
import re
from pyspark.sql.functions import udf
from pyspark.sql.types import StructType, StructField, StringType, MapType, ArrayType, IntegerType


# 创建 SparkSession
spark = SparkSession.builder \
    .appName("Data Cleaning and Deduplication") \
    .getOrCreate()

from pyspark.sql import SparkSession, functions as F



def clean_text(text):
    """
    清洗文本，提取中日韩英文字母，去除 HTML 转义符与标签。
    """
    if not isinstance(text, str):
        return text  # 如果不是字符串类型，直接返回

    # 去除 HTML 转义符
    text = html.unescape(text)

    # 去除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 提取中日韩英与字母字符
    text = re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\w\s]+', text)

    # 拼接成清洗后的文本
    return ' '.join(text).strip()

clean_text_udf = udf(clean_text,StringType())


def load_data_from_db(db_host, db_port, db_user, db_pass, db_name):
    # 创建 JDBC URL
    jdbc = f"jdbc:mysql://{db_host}:{db_port}/{db_name}?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC&autoReconnect=true"

    # 连接属性
    connection_properties = {
        "user": db_user,
        "password": db_pass,
        "driver": "com.mysql.cj.jdbc.Driver"
    }

    # 从数据库中读取数据表
    program = spark.read.jdbc(url=jdbc, table="program", properties=connection_properties)
    episode = spark.read.jdbc(url=jdbc, table="episodes", properties=connection_properties)

    # 过滤并选择 `program` 中状态为 1 的有效数据
    program_df = program.filter(F.col("state") == 1).select(
        F.col("id").alias("program_id"),
        clean_text_udf(F.col("title")).alias("title"),
        F.col("description"),
        F.col("poster"),
    )

    # 选择 `episode` 的相关字段
    episode_df = episode.select(
        F.col("sort_number"),
        F.col("stage"),
        F.col("program_id")
    )

    # 将相同 `program_id` 下的 `stage` 合并为一个列表
    play_url_df = episode_df.groupBy("program_id").agg(
        F.collect_list("stage").alias("play_url")
    )

    # 将 `play_url` 与 `program_df` 合并
    final_program_df = program_df.join(play_url_df, on="program_id", how="left")

    return final_program_df


def load_data(fileName):
    # 模拟从数据库加载现有数据
    with open(fileName, 'r') as f:
        data = json.load(f)

    schema = StructType([
        StructField("title", StringType(), True),
        StructField("play_url", MapType(StringType(), StringType()), True),
        StructField("description", StringType(), True),
        StructField("actor", ArrayType(StringType()), True),
        StructField("director", ArrayType(StringType()), True),
        StructField("vod_id", IntegerType(), True),
        StructField("poster", StringType(), True),
    ])

    # 创建 DataFrame
    existing_df = spark.createDataFrame(data, schema=schema)

    # 清洗 title 字段
    cleaned_df = existing_df.withColumn("title", clean_text_udf(F.col("title")))
    cleaned_df = cleaned_df.withColumn("description", clean_text_udf(F.col("description")))

    return cleaned_df


def update_play_url(existing_play_url, new_play_url):
    """
    比较两个 play_url 字典，并将新的分集合并到旧的 play_url 中。
    如果分集已存在且链接相同，则保留。
    如果分集不存在或链接不同，则更新。
    """
    updated_play_url = existing_play_url.copy()

    for key, url in new_play_url.items():
        if key not in updated_play_url or updated_play_url[key] != url:
            updated_play_url[key] = url  # 更新或新增分集

    return updated_play_url





def check_and_update_new_data(new_dataFrame, existing_dateFrame):
    # 将 existing_dateFrame 转为字典格式 (在内存中加速查找)
    existing_dict = {row['title']: row for row in existing_dateFrame.collect()}

    # 保存新增节目和有差异的节目
    new_programs = []
    updated_programs = []


    # 遍历所有新数据的行
    for row in new_dataFrame.collect():
        new_title = row['title']
        new_play_url = row['play_url']  # 假定是 MapType：{"第01集": "url1", "第02集": "url2", ...}
        new_description = row["description"]
        new_poster = row["poster"]
        new_actor = row["actor"]
        new_director = row["director"]

        # 合并演员与导演标签
        new_tags = new_actor + new_director



        if new_title not in existing_dict:
            # 如果是新增的节目，写入所有字段
            new_programs.append((new_title, new_play_url, new_description, new_poster, new_tags, new_actor))
        else:
            # 如果是已存在的节目，对比 play_url 差异
            existing_row = existing_dict[new_title]
            existing_id = existing_row['program_id']  # 获取已存在节目的ID
            existing_play_url_list = existing_row["play_url"] # 确保得到的是一个列表或空列表


            # 检查 existing_play_url_list 的类型是否为列表
            if not isinstance(existing_play_url_list, list):
                existing_play_url_list = []

            # 提取新的分集名称
            #new_episode_keys = set(new_play_url.keys())  # 新数据的所有分集名称 (比如：{"第01集", "第02集", "第03集"})

            # 找出新增或更新的分集
            updated_play_url = { k : v for k, v in new_play_url.items() if standardVideoStage(k,row["title"]) not in existing_play_url_list}

            if updated_play_url:
                # 如果存在差异，只保留 id, title, play_url (MapType)
                updated_programs.append((existing_id, new_title, updated_play_url,new_tags))

    # 创建 DataFrames 用于返回
    new_programs_df = None
    updated_programs_df = None

    if new_programs:
        new_programs_df = spark.createDataFrame(
            new_programs,
            ["title", "play_url", "description", "poster", "tags", "actor"]
        )

    if updated_programs:
        updated_programs_df = spark.createDataFrame(
            updated_programs,
            ["id", "title", "play_url","tags"]
        )

    return new_programs_df, updated_programs_df




def main():
    # 模拟加载现有数据
    existing_df = load_data_from_db("127.0.0.1","3306","root","simonks1012","yimitv")
    # 新数据
    new_data_json = load_data("./20250336_14.json")

    # 检查与更新数据
    new_df,update_df = check_and_update_new_data(new_data_json, existing_df)

    if new_df:
        programs = programDFToParams(new_df)
    else:
        programs = None

    if update_df:
        videos = updateDFToParams(update_df)
    else:
        videos = None

    if isEmptyArray(programs) and isEmptyArray(videos):
        print("暂时无更新")
    else:
        # 初始化客户端
        cli = StudioClient(host="http://localhost:8080",username="jk2023",password="simonks1012")
        # 假如节目不为空
        if programs:
            if cli.BatchCreatePrograms(param=BatchCreateProgramsParam(programs=programs)):
                print(f"新建节目 {len(programs)}个")

        # 假如视频不为空
        if videos:
            if cli.BatchCreateVideos(params=BatchCreateVideosParam(videos=videos)):
                print(f"更新视频 {len(videos)}个")

def isEmptyArray(obj)->bool:
    if obj is None:
        return True
    return isinstance(obj, list) and len(obj) == 0


def standardVideoStage(videoStage:str,programTitle:str):
    return f"{programTitle} {videoStage}"


def parseSortNumber(text: str) -> int:
    QUALITY_RANKING = {
        "LD": 0,  # 标清
        "SD": 1,  # 标准清晰度
        "HD": 2,  # 高清
        "UHD": 3,  # 全高清
        "2K": 4,  # 2K
        "4K": 5,  # 4K
        "8K": 6  # 8K
    }

    # 匹配 "第X集" 或纯数字
    match = re.search(r'第(\d+)集|\b\d+\b', text)

    if match:
        result = match.group(0)

        # 提取并返回数字集数
        if result.isdigit():
            return int(result)

        # 提取 "第X集" 中的数字
        if result.startswith("第"):
            return int(re.search(r'\d+', result).group())

    # 匹配清晰度
    quality_match = re.search(r'\b(LD|SD|HD|UHD|2K|4K|8K)\b', text, re.IGNORECASE)
    if quality_match:
        quality = quality_match.group(0).upper()
        return QUALITY_RANKING.get(quality, None)

    return 0


def programDFToParams(df)->List[CreateProgramParam]:
    programEpisodes = {}

    for n in df.collect():
        episodes = []

        for stage, url in n["play_url"].items():
            episodes.append(AddEpisodesParam(
                video_title=standardVideoStage(videoStage=stage, programTitle=n["title"]),
                video_description=n["description"],
                video_play_link=url,
                source_from="other",
                sort_number=parseSortNumber(stage),
                episode_stage=standardVideoStage(videoStage=stage, programTitle=n["title"]),
            ))
        programEpisodes[n["title"]] = episodes

    # 生成新建节目参数
    return [
        CreateProgramParam(
            title=n["title"],
            description=n["description"],
            show_subtitle="",
            poster=n["poster"],
            thumb="",
            tags=n["tags"],
            is_adult=False,
            price=0.0,
            category_id="tv",
            episodes=programEpisodes.get(n["title"]),
            is_subscribe_program=True,
        )
        for n in df.collect()
    ]

def updateDFToParams(df)->List[CreateVideoParam]:
    videos = []
    # 循环获取
    for p in df.collect():
        for stage, url in p["play_url"].items():
            videos.append(
                CreateVideoParam(
                    title=standardVideoStage(stage, p["title"]),
                    description="",
                    play_link=url,
                    program=AddProgramParam(
                        program_id=p["id"],
                        sort_number=parseSortNumber(stage),
                        stage=standardVideoStage(stage, p["title"])
                    ),
                    tags=p["tags"],
                    thumb=""
                )
            )
    return videos



if __name__ == "__main__":
    main()

#spark-submit
#spark-submit --master local[*] --jars /Users/liangyongbin/PycharmProjects/crawel/mysql-connector-java.jar --deploy-mode client ./spark.py
'''

kubectl -n argo create token ack-argo-server

'''