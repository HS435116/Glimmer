import os
import sys


if sys.version_info < (3, 10):
    raise SystemExit(f"Glimmer server 需要 Python >= 3.10，当前为 {sys.version.split()[0]}")


import uvicorn


if __name__ == '__main__':
    host = os.environ.get('GLIMMER_HOST') or '0.0.0.0'
    port = int(os.environ.get('GLIMMER_PORT') or 8000)

    # 开发环境可开启 reload；Windows + SQLite 在 reload 监控全目录时容易因为数据库文件变更触发异常退出。
    # 因此默认关闭 reload；需要时请显式设置：GLIMMER_RELOAD=1
    reload_flag = (os.environ.get('GLIMMER_RELOAD') or '0').strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    log_level = (os.environ.get('GLIMMER_LOG_LEVEL') or 'info').strip().lower()

    server_dir = os.path.dirname(os.path.abspath(__file__))

    kwargs = {
        'host': host,
        'port': port,
        'reload': reload_flag,
        'log_level': log_level,
    }
    if reload_flag:
        kwargs.update(
            {
                'reload_dirs': [server_dir],
                'reload_excludes': ['*.sqlite', '*.sqlite*', '*.db', '*.db*', '*.bak*', '__pycache__', '.git'],
            }
        )

    uvicorn.run('app.main:app', **kwargs)

