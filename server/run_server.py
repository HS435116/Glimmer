import os
import uvicorn


if __name__ == '__main__':
    host = os.environ.get('GLIMMER_HOST') or '0.0.0.0'
    port = int(os.environ.get('GLIMMER_PORT') or 8000)

    # 开发环境建议开启 reload；生产环境务必关闭（更稳定）
    reload_flag = (os.environ.get('GLIMMER_RELOAD') or '1').strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    log_level = (os.environ.get('GLIMMER_LOG_LEVEL') or 'info').strip().lower()

    uvicorn.run('app.main:app', host=host, port=port, reload=reload_flag, log_level=log_level)
