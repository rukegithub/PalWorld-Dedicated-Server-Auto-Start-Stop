import subprocess
import logging
import time
import threading
from settings import Settings
import traceback

# 현재 서버 상태를 저장하는 변수
currentServerInfo = {
    "running": False,  # 서버 실행 여부
    "playerCount": 0,  # 플레이어 수
    "players": []      # 플레이어 목록
}

# 서버 시작 상태 변수
isPalWorldServerStarting = False
ServerStartingCoolTime = 5  # 서버 시작 쿨타임 (초)
lastServerStartedTime = 0  # 마지막 서버 시작 시간
ServerStoppingCoolTime = 5  # 서버 종료 쿨타임 (초)
lastServerStoppedTime = 0  # 마지막 서버 종료 시간

# 종료된 서버 확인을 위한 변수
triggeredTimeCheckStoppedEvent = -1  # 종료 이벤트가 트리거된 시간
isTriggeredCheckStoppedEvent = False  # 종료 이벤트가 실행 중인지 여부

# PalWorld 프로세스가 실행 중인지 확인하는 함수
def isPalWorldProcessRunning():
    try:
        # `pgrep` 명령어를 사용해 PalWorld 프로세스가 실행 중인지 확인
        result = subprocess.run(['pgrep', '-f', Settings.palworldMainProcessName], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0  # returncode가 0이면 프로세스가 실행 중
    except Exception as e:
        logging.error(f"PalWorld 프로세스 확인 중 오류 발생: {e}")
        return False

# RCON 명령어를 보내는 함수
def sendRCONCommand(command):
    try:
        console = Console(host=Settings.palworldRCONHost, port=Settings.palworldRCONPort, password=Settings.palworldAdminPassword)
        response = console.command(command)
        logging.info(f"[PALWORLD_RCON]: {str(response)}")
        console.close()
        return response
    except Exception as e:
        logging.error(f"RCON 명령어 실행 중 오류 발생. 명령어={command}")
        logging.error(traceback.format_exc())
        return None

# 서버를 시작하는 함수
def startServer():
    from autoStart import closePalworldPortSocket

    global isPalWorldServerStarting, lastServerStartedTime, ServerStartingCoolTime, lastServerStoppedTime, ServerStoppingCoolTime
    logging.info("서버 시작이 트리거되었습니다.")
    palworldExePath = Settings.palworldExePath  # 서버 실행 파일 경로 (리눅스 쉘 스크립트)
    currentTime = time.time()

    # 서버가 이미 실행 중이면 실행을 방지
    if isPalWorldProcessRunning():
        logging.error("서버가 이미 실행 중입니다. 다시 시작할 수 없습니다.")
        return False

    # 서버 시작 중일 때 다시 시작을 방지
    if isPalWorldServerStarting:
        logging.warning("Palworld 서버가 이미 시작 중입니다.")
        return False

    # 서버 시작 쿨타임 확인
    if currentTime - lastServerStartedTime < ServerStartingCoolTime:
        logging.warning("서버를 너무 빨리 여러 번 시작하려 했습니다. 이 시도는 무시됩니다.")
        return False

    # 서버 종료 쿨타임 확인
    if currentTime - lastServerStoppedTime < ServerStoppingCoolTime:
        logging.warning("서버를 종료한 후 너무 빨리 다시 시작하려 했습니다. 이 시도는 무시됩니다.")
        return False

    # 서버 종료 이벤트가 실행 중일 때 서버 시작을 방지
    if isStopEventRunning():
        logging.warning(f"서버 종료 이벤트가 실행 중입니다. 서버 시작을 무시합니다.")
        return False

    # 열린 소켓이 있을 경우 닫기
    closePalworldPortSocket()

    returnVal = True

    # 서버 실행 (리눅스에서 쉘 스크립트로 서버 실행)
    try:
        isPalWorldServerStarting = True
        subprocess.run(["bash", palworldExePath], check=True)  # 리눅스 쉘 스크립트 실행
    except subprocess.CalledProcessError as e:
        logging.error(f"PalWorld 실행 파일 실행 중 오류 발생: {e}")
        returnVal = False
    finally:
        isPalWorldServerStarting = False
        lastServerStartedTime = time.time()

    return returnVal

# 프로세스를 종료하는 함수
def terminateProcess(processName):
    try:
        # `pgrep` 명령어로 프로세스 ID 확인 후, `kill` 명령어로 종료
        result = subprocess.run(['pgrep', '-f', processName], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            pid = result.stdout.decode().strip()
            subprocess.run(['kill', pid])
            logging.info(f"프로세스 {processName} (PID: {pid}) 종료됨.")
        else:
            logging.error(f"프로세스 {processName}을 찾을 수 없습니다.")
    except Exception as e:
        logging.error(f"프로세스 {processName} 종료 중 오류 발생: {e}")

# PalWorld 프로세스가 종료되었는지 확인하고, 종료되었으면 listenPalworldAccess 함수 실행
def checkIsStoppedPalworldProcessCore(timeout=60):
    from autoStart import listenPalworldAccess

    global isTriggeredCheckStoppedEvent, triggeredTimeCheckStoppedEvent
    triggeredTimeCheckStoppedEvent = time.time()
    while True:
        # 프로세스가 종료되었는지 확인
        if not isPalWorldProcessRunning():
            logging.info("PalWorld 프로세스 종료 확인됨")
            time.sleep(1)
            listenPalworldAccess()  # PalWorld 접속 대기
            break

        currentTime = time.time()
        # 타임아웃 시간 내에 종료되지 않으면 종료
        if currentTime - triggeredTimeCheckStoppedEvent > timeout:
            break

        time.sleep(1)
    isTriggeredCheckStoppedEvent = False

# 서버 종료 이벤트가 실행 중인지 확인하는 함수
def isStopEventRunning():
    return isTriggeredCheckStoppedEvent

# 서버를 종료하는 함수
def stopServer(delaySeconds, force=False):
    global lastServerStoppedTime, ServerStoppingCoolTime, isTriggeredCheckStoppedEvent
    logging.info("서버 종료가 트리거되었습니다.")

    # 종료 이벤트가 실행 중이 아니면 새로 시작
    if not isTriggeredCheckStoppedEvent:
        isTriggeredCheckStoppedEvent = True
        thread = threading.Thread(target=checkIsStoppedPalworldProcessCore)
        thread.start()

    if force:
        # 강제 종료 시, 프로세스 종료
        terminateProcess(Settings.palworldMainProcessName)
    else:
        # 서버가 실행 중이지 않으면 종료할 필요 없음
        if not isPalWorldProcessRunning():
            logging.error("서버가 실행 중이지 않아 종료할 수 없습니다.")
            return

        # 서버 종료 쿨타임 확인
        currentTime = time.time()
        if currentTime - lastServerStoppedTime < ServerStoppingCoolTime:
            logging.warning("서버를 너무 빨리 여러 번 종료하려 했습니다. 이 시도는 무시됩니다.")
            return

        if delaySeconds < 1.0:
            delaySeconds = 1.0
        sendRCONCommand(f"Shutdown {delaySeconds} 서버가 종료됩니다.")

    lastServerStoppedTime = time.time()

# 서버의 플레이어 정보를 업데이트하는 함수
def updateCurrentServerInfo():
    global currentServerInfo
    try:
        currentTime = time.time()
        # 서버가 실행 중이지 않거나 종료 이벤트가 실행 중이면 업데이트하지 않음
        if not isPalWorldProcessRunning() or isTriggeredCheckStoppedEvent or (currentTime - lastServerStoppedTime < ServerStoppingCoolTime):
            currentServerInfo["running"] = False
            currentServerInfo["playerCount"] = 0
            currentServerInfo["players"] = []
            return currentServerInfo

        currentServerInfo["running"] = True

        # 플레이어 수 가져오기
        ShowPlayers = sendRCONCommand("ShowPlayers")
        SplitText = ShowPlayers.splitlines()
        currentServerInfo["playerCount"] = len(ShowPlayers.splitlines()) - 1

        # 플레이어 이름 가져오기
        if currentServerInfo["playerCount"] >= 1:
            currentServerInfo["players"] = []
            for i in range(currentServerInfo["playerCount"]):
                currentServerInfo["players"].append(SplitText[i + 1].split(','))
        else:
            currentServerInfo["players"] = []

        return currentServerInfo

    except Exception as e:
        logging.error(f"서버 정보 업데이트 중 오류 발생, {e}")
        logging.error(traceback.format_exc())
        return None

# 서버 상태를 반환하는 함수
def getServerStatus():
    # 서버가 실행 중이지 않으면 False 반환
    if not isPalWorldProcessRunning():
        return False
