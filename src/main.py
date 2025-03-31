from settings import Settings, readSettings
from webServer import runWebServer
from autoStart import listenPalworldAccess
from autoStop import checkEventStopServer
from logging.handlers import TimedRotatingFileHandler
import logging
import traceback

# logs 폴더가 없으면 생성
if not os.path.exists('logs'):
    os.makedirs('logs')

# 로그 파일 핸들러 설정
log_handler = TimedRotatingFileHandler(
    'logs/app.log',               # 기본 로그 파일 이름
    when='midnight',          # 매일 자정에 로그 파일 롤링
    interval=1,               # 1일마다 롤링
    backupCount=30,           # 최대 30일(한 달)치 로그 보관
    encoding='utf-8',         # 로그 파일 인코딩
    delay=False               # 로그 파일이 생성되자마자 바로 기록
)

# 로그 포맷 설정
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)

if __name__ == '__main__':
    try:
        # Configure logging to write messages to the console and a file
        # 로그 설정
        logging.basicConfig(
            level=logging.INFO,
            handlers=[log_handler, logging.StreamHandler()]  # 콘솔에도 출력
        )

        # read settings if settings.json exists
        readSettings("settings.json")

        if Settings.useAutoStart:
            listenPalworldAccess()

        if Settings.useAutoStop:
            checkEventStopServer()

        if Settings.useWebServer:
            runWebServer()

    except Exception as e:
        logging.error(f"Error from main routine: {e}")
        logging.error(traceback.format_exc())