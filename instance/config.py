# instance/config.py
# 这个文件用于本机私有配置（建议不要提交到 git）

SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:123456@127.0.0.1:3306/certs_db?charset=utf8mb4"

# 可选：如果你要关 FULLTEXT 就改成 False
CERTS_ENABLE_FULLTEXT = True
