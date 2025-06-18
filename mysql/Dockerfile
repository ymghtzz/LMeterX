FROM mysql:5.7

# 设置环境变量
ENV MYSQL_ROOT_PASSWORD=lmeterx123
ENV MYSQL_DATABASE=lmeterx

# 复制初始化脚本
COPY ../init_db.sql /docker-entrypoint-initdb.d/

# 设置 MySQL 配置
CMD ["mysqld", "--default-authentication-plugin=mysql_native_password", "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci", "--init-connect=SET NAMES utf8mb4"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD || exit 1

# 暴露端口
EXPOSE 3306
