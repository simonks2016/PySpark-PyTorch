FROM docker.m.daocloud.io/bitnami/spark:3.5.5

USER root

# 获取当前 Debian 版本并替换阿里云源
RUN mv /etc/apt/sources.list /etc/apt/sources.list.bak && \
    echo "deb http://mirrors.aliyun.com/debian $(grep VERSION_CODENAME /etc/os-release | cut -d= -f2) main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security $(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)-security main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian $(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)-updates main contrib non-free" >> /etc/apt/sources.list && \
    apt update && apt install -y rsync openssh-server python3 python3-pip libmariadb-dev

# 配置 pip 使用清华 PyPI 镜像源
RUN mkdir -p /root/.pip && echo "[global]\nindex-url = https://mirrors.aliyun.com/pypi/simple" > /root/.pip/pip.conf

# 复制emi sdk
COPY emi_sdk-0.1.1b0-py3-none-any.whl /tmp/
# 更新 pip
RUN python3 -m pip install --upgrade pip
# 安装emi组件
RUN pip install /tmp/emi_sdk-0.1.1b0-py3-none-any.whl
RUN pip install -i https://mirrors.aliyun.com/pypi/simple pyspark==3.5.5 requests beautifulsoup4 uuid
RUN pip install -i https://mirrors.aliyun.com/pypi/simple --no-cache-dir SQLAlchemy pymysql
RUN pip install -i https://mirrors.aliyun.com/pypi/simple --no-cache-dir torch torchvision torchaudio scikit-learn
RUN pip install -i https://mirrors.aliyun.com/pypi/simple --no-cache-dir oss2


# 复制 MySQL Connector 和 Hadoop 组件
COPY mysql-connector-java.jar /opt/bitnami/spark/jars/mysql-connector-java.jar
COPY hadoop-common.jar /opt/bitnami/spark/jars/hadoop-common.jar
COPY hadoop-auth.jar /opt/bitnami/spark/jars/hadoop-auth.jar
COPY jmx_prometheus_javaagent-0.16.1.jar /opt/bitnami/spark/jars/jmx_prometheus_javaagent-0.16.1.jar

ADD --chown=1001:1001 --chmod=644 https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aliyun/3.3.4/hadoop-aliyun-3.3.4.jar /opt/bitnami/spark/jars/
ADD --chown=1001:1001 --chmod=644 https://repo1.maven.org/maven2/com/aliyun/oss/aliyun-sdk-oss/3.17.4/aliyun-sdk-oss-3.17.4.jar /opt/bitnami/spark/jars/
ADD --chown=1001:1001 --chmod=644 https://repo1.maven.org/maven2/org/jdom/jdom2/2.0.6.1/jdom2-2.0.6.1.jar /opt/bitnami/spark/jars/

# 公开 SSH 端口
EXPOSE 22
# 切换回 bitnami/spark 默认用户
USER 1001








