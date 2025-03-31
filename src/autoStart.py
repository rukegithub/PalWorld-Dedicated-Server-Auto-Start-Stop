# autoStart.py

import socket
from settings import Settings
from palWorldControl import isPalWorldProcessRunning, startServer
import logging
import traceback
import select

# 전역 변수 선언
sock = None  # 소켓 객체
timeout = 5.0  # 5초마다 체크
isBreak = False  # 실행 중단 플래그

# PalWorld 서버 포트 사용 가능 여부 확인
def isPortAvailable(port):
    """포트 가용성 확인"""
    test_socket = None
    try:
        # 1. UDP 소켓 생성
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 2. localhost 바인딩
        test_socket.bind(("localhost", port))
        return True
    
    except OSError:  # OSError 캐치
        return False
    
    finally:  # 3. 리소스 해제 보장
        if test_socket:
            test_socket.close()


# PalWorld 서버 포트 감시를 위한 소켓 열기
def openPalworldPortSocket():
    try:
        global sock, isBreak

        # 기존 소켓이 열려 있으면 먼저 닫기
        if sock is not None:
            closePalworldPortSocket()  # 이미 열려 있으면 소켓 닫기
        
        isBreak = False  # 중단 플래그 초기화
        palworldServerIP = Settings.palworldServerIP  # 설정에서 IP 가져오기
        palworldServerPort = Settings.palworldServerPort  # 설정에서 포트 가져오기
        
        # UDP 소켓 생성 및 바인딩
        logging.info(f"PalWorld 서버 연결 시도를 감지하기 위해 포트 {palworldServerPort}를 엽니다.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((palworldServerIP, palworldServerPort))
        return True
    except Exception as e:
        logging.error(f"openPalworldPortSocket 에러: {e}")
        logging.error(traceback.format_exc())
        isBreak = True  # 에러 발생 시 중단 플래그 설정
        return False


# 소켓 닫기
def closePalworldPortSocket():
    logging.info("closePalworldPortSocket")
    global sock, isBreak
    isBreak = True  # 실행 중단 플래그 설정
    if sock:
        try:
            sock.close()
            sock = None
            return True
        except Exception as e:
            logging.error(f"closePalworldPortSocket 에러: {e}")
            logging.error(traceback.format_exc())
    return False


# PalWorld 서버 접속 시도 감지 핵심 로직
def listenPalworldAccessCore():
    # 이미 PalWorld 프로세스가 실행 중이면 종료
    if isPalWorldProcessRunning():
        return

    # 포트 사용 불가능하면 종료
    if not isPortAvailable(Settings.palworldServerPort):
        logging.error(f"Palworld 프로세스가 실행 중이지 않지만, 포트 {Settings.palworldServerPort}를 열 수 없습니다.")
        return
    
    # 소켓 열기 실패하면 종료
    if not openPalworldPortSocket():
        logging.error(f"Palworld 연결 패킷 대기를 위한 소켓을 열 수 없습니다.")
        return

    logging.info("PalWorld 서버 연결 시도를 감지 중입니다.")

    isServerStarted = False  # 서버 시작 여부 플래그

    while not isBreak:
        try:
            readable, _, _ = select.select([sock], [], [], timeout)
            if readable:
                data, addr = sock.recvfrom(1024)
                hex_data = " ".join(format(byte, "02X") for byte in data)

                if data.startswith(Settings.firstPacketPattern):
                    logging.info(f"[LISTEN_PALWORLD_PORT][DETECTED] {addr}: {hex_data}")
                    logging.info("서버 연결 시도에 해당하는 패킷이 감지되었습니다. 서버를 시작합니다.")
                    isServerStarted = True
                    break
                else:
                    logging.info(f"[LISTEN_PALWORLD_PORT][IGNORED] {addr}: {hex_data}")

        except UnicodeDecodeError as e:
            logging.error(f"{addr}에서 데이터 디코딩 에러: {e}")
        except socket.error as e:
            logging.error(f"소켓 오류: {e}")
        except Exception as e:
            logging.error(f"알 수 없는 오류: {e}")

    # 서버 시작 플래그가 True이면 서버 시작
    if isServerStarted:
        closePalworldPortSocket()
        startServer()


# PalWorld 접속 감지 시작 (스레드로 실행)
def listenPalworldAccess():
    logging.info("listenPalworldAccess 시작")

    try:
        listenPalworldAccessCore()
    except Exception as e:
        logging.error(f"listenPalworldAccessCore 실패: {str(e)}")