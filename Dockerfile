FROM python:3.10-alpine

# 设置工作目录
WORKDIR /app

# 设置时区和环境变量以保证输出无缓存
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1

# 安装系统时区文件并配置
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码和静态网页文件
COPY iptv_resolver.py index.html ./

# 启动服务
CMD ["python", "iptv_resolver.py"]
