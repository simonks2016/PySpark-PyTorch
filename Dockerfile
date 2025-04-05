# 使用 Python 3.8-slim 作为基础镜像，保证 Python 版本为 3.8
FROM python:3.8-slim

# 安装 OpenJDK、wget、curl、unzip 等必备工具
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk wget curl unzip && \
    rm -rf /var/lib/apt/lists/*

# 设置 Spark 版本及相关环境变量
ENV SPARK_VERSION=3.5.5
ENV SPARK_PACKAGE=spark-${SPARK_VERSION}-bin-hadoop3
ENV SPARK_HOME=/opt/spark

# 将本地预先下载的 Spark 压缩包复制到镜像中并解压
RUN wget -q https://mirrors.aliyun.com/apache/spark/spark-3.5.5/spark-3.5.5-bin-hadoop3.tgz -O /tmp/spark.tgz && \
    tar -xzf /tmp/spark.tgz -C /opt && \
    mv /opt/${SPARK_PACKAGE} ${SPARK_HOME} && \
    rm /tmp/spark.tgz

# 将预先下载的 hadoop-aliyun jar 包复制到 Spark 的 jars 目录下
COPY /jars/hadoop-aliyun-3.0.0.jar ${SPARK_HOME}/jars/
COPY /jars/mysql-connector-java.jar ${SPARK_HOME}/jars/
COPY /jars/hadoop-common.jar ${SPARK_HOME}/jars/
COPY /jars/hadoop-auth.jar ${SPARK_HOME}/jars/
COPY /jars/jindo-sdk-6.8.2.jar ${SPARK_HOME}/jars/
COPY /jars/jindo-core-6.8.2.jar ${SPARK_HOME}/jars/


# 将预先下载的 aliyun-oss-java.zip 复制到镜像中，解压并将其中的 jar 文件复制到 Spark 的 jars 目录下
COPY aliyun-oss-java.zip /tmp/aliyun-oss-java.zip
RUN unzip /tmp/aliyun-oss-java.zip -d /tmp/aliyun-oss-java && \
    cp /tmp/aliyun-oss-java/*.jar ${SPARK_HOME}/jars/ && \
    rm -rf /tmp/aliyun-oss-java.zip /tmp/aliyun-oss-java

# 设置 OSS 认证信息（构建时通过 --build-arg 传入，也可在运行容器时通过环境变量覆盖）
ARG OSS_ACCESS_KEY_ID=""
ARG OSS_SECRET_ACCESS_KEY=""
ENV OSS_ACCESS_KEY_ID=${OSS_ACCESS_KEY_ID}
ENV OSS_SECRET_ACCESS_KEY=${OSS_SECRET_ACCESS_KEY}

COPY emi_sdk-0.1.1b0-py3-none-any.whl /tmp/emi_sdk-0.1.1b0-py3-none-any.whl

# 升级 pip 并配置为清华镜像源，加快包安装速度
RUN pip install --upgrade pip && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装所需的 Python 包：requests、oss2、torch、scikit-learn 和 pyspark
RUN pip install requests oss2 torch scikit-learn pyspark uuid
RUN pip install /tmp/emi_sdk-0.1.1b0-py3-none-any.whl

# 将 Spark 的 bin 目录加入 PATH
ENV PATH="${SPARK_HOME}/bin:${PATH}"

WORKDIR /opt

# 创建入口脚本，用于通过 spark-submit 运行 OSS 上的 pyspark 文件
RUN echo '#!/bin/bash' > /opt/entrypoint.sh && \
    echo 'if [ -z "$OSS_PYSPARK_FILE" ]; then' >> /opt/entrypoint.sh && \
    echo '  echo "Error: OSS_PYSPARK_FILE environment variable is not set."' >> /opt/entrypoint.sh && \
    echo '  exit 1' >> /opt/entrypoint.sh && \
    echo 'fi' >> /opt/entrypoint.sh && \
    echo 'echo "Starting spark job from OSS file: $OSS_PYSPARK_FILE"' >> /opt/entrypoint.sh && \
    echo 'spark-submit --master local --deploy-mode client \\' >> /opt/entrypoint.sh && \
    echo '  --conf spark.hadoop.fs.oss.accessKeyId=$OSS_ACCESS_KEY_ID \\' >> /opt/entrypoint.sh && \
    echo '  --conf spark.hadoop.fs.oss.secretAccessKey=$OSS_SECRET_ACCESS_KEY \\' >> /opt/entrypoint.sh && \
    echo '  $OSS_PYSPARK_FILE' >> /opt/entrypoint.sh && \
    chmod +x /opt/entrypoint.sh

# 容器启动时执行入口脚本
CMD ["/opt/entrypoint.sh"]


