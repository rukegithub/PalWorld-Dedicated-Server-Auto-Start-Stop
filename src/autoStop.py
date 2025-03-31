import logging
import traceback
import schedule
import time
import threading
from settings import Settings
from palWorldControl import isPalWorldProcessRunning, stopServer, updateCurrentServerInfo, isStopEventRunning

stopServerVariables = {
    "stopEventTriggeredTime": 1.0E+100,
    "isRunningStopwatchToStopServer": False,
    "leftTimeToStopServer": -1
}
stop_schedule = threading.Event()
stopServerVariablesLock = threading.Lock()  # 동기화용 Lock

def checkEventStopServerCore():
    try:
        global stopServerVariables

        with stopServerVariablesLock:
            if not isPalWorldProcessRunning():
                stopServerVariables["isRunningStopwatchToStopServer"] = False
                return

            if isStopEventRunning():
                logging.info(f"Stop event is running. checkEventStopServerCore ignored")
                return

            currentServerInfo = updateCurrentServerInfo()
            if currentServerInfo is None:
                logging.warn("Failed to retrieve server info. Skipping stop event check this time.")
                return

            if currentServerInfo["playerCount"] > 0:
                stopServerVariables["isRunningStopwatchToStopServer"] = False
                return

            currentTime = time.time()
            if not stopServerVariables["isRunningStopwatchToStopServer"]:
                stopServerVariables["stopEventTriggeredTime"] = currentTime
                stopServerVariables["isRunningStopwatchToStopServer"] = True

            passedTime = currentTime - stopServerVariables["stopEventTriggeredTime"]
            if passedTime >= Settings.ServerAutoStopSeconds:
                stopServer(1)
                with stopServerVariablesLock:
                    stopServerVariables["stopEventTriggeredTime"] = 1.0E+100  # 초기화
                    stopServerVariables["isRunningStopwatchToStopServer"] = False  # 타이머 종료
                    stopServerVariables["leftTimeToStopServer"] = -1  # 남은 시간 리셋
            else:
                stopServerVariables["leftTimeToStopServer"] = Settings.ServerAutoStopSeconds - passedTime

    except Exception as e:
        logging.error(f"Error from checkEventStopServerCore: {e}")
        logging.error(traceback.format_exc())

def runSchedule():
    while not stop_schedule.is_set():
        interval = Settings.ServerAutoStopCheckInterval
        schedule.run_pending()
        time.sleep(min(interval, 1))

def stop_scheduler():
    stop_schedule.set()

def checkEventStopServer():
    global stopServerVariables

    logging.info("Start checkEventStopServer")

    checkEventStopServerCore()

    schedule.every(Settings.ServerAutoStopCheckInterval).seconds.do(checkEventStopServerCore)

    thread = threading.Thread(target=runSchedule, daemon=True)
    thread.start()
