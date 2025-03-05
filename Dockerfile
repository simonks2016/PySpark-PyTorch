FROM docker.m.daocloud.io/bitnami/spark:latest

USER root

# 获取当前 Debian 版本并替换阿里云源
RUN mv /etc/apt/sources.list /etc/apt/sources.list.bak && \
    echo "deb http://mirrors.aliyun.com/debian $(grep VERSION_CODENAME /etc/os-release | cut -d= -f2) main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security $(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)-security main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian $(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)-updates main contrib non-free" >> /etc/apt/sources.list && \
    apt update && apt install -y rsync openssh-server python3 python3-pip libmariadb-dev

# 配置 pip 使用清华 PyPI 镜像源
RUN mkdir -p /root/.pip && echo "[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple" > /root/.pip/pip.conf

# 更新 pip
RUN python3 -m pip install --upgrade pip
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pyspark==3.5.5 requests beautifulsoup4 torch torchvision torchaudio scikit-learn uuid SQLAlchemy pymysql

# 复制 MySQL Connector 和 Hadoop 组件
COPY mysql-connector-java.jar /opt/bitnami/spark/jars/mysql-connector-java.jar
COPY hadoop-common.jar /opt/bitnami/spark/jars/hadoop-common.jar
COPY hadoop-auth.jar /opt/bitnami/spark/jars/hadoop-auth.jar
# 复制 Hadoop 配置
COPY core-site.xml /opt/bitnami/spark/conf/core-site.xml
COPY hdfs-site.xml /opt/bitnami/spark/conf/hdfs-site.xml


# 公开 SSH 端口
EXPOSE 22
# 切换回 bitnami/spark 默认用户
USER 1001

#CMD ["/opt/bitnami/spark/sbin/start-master.sh", "--host", "0.0.0.0"]








