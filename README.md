# PyQuadDir — Quad-View Multi-Tab Desktop File Explorer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Platform: Windows / Cross-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6.svg)](#)

**PyQuadDir**는 Windows 로컬 드라이브(`C:\`, `D:\` 등)와 파일 시스템을 한눈에 제어하는 **4분할(Quad-View) 다중 탭 데스크톱 파일 탐색기**입니다.

> *Inspired by the classic quad-pane file manager concept (such as Q-Dir), cleanly implemented from scratch in pure Python with a Triple-Engine architecture (`PySide6` / `PyQt6` / `Tkinter`).*

---

## ✨ 주요 기능 (Key Features)

1. **6가지 화면 분할 레이아웃 실시간 전환 (`Ctrl+1` ~ `Ctrl+6`)**
   * `⊞ 4분할 (2×2 격자)`, `◫ 2분할 (좌/우)`, `⊟ 2분할 (상/하)`, `◧ 3분할 (좌1·우2)`, `⬒ 3분할 (상1·하2)`, `⬜ 1분할 (단일 최대화)` 및 `⚖️ 창 비율 균등화` 원클릭 지원
2. **패널별 독립 다중 탭(Multi-Tab) 탐색**
   * 각 분할 창마다 독립된 다중 탭 보유 (`Ctrl+T` 새 탭, `Ctrl+W` 탭 닫기, 폴더 **마우스 휠 클릭**으로 즉시 새 탭에서 열기)
   * 패널별 뒤로/앞으로 가기 히스토리, 상위 폴더 이동, 실시간 파일명/확장자 즉시 필터링(`🔍`)
3. **창 간 드래그 앤 드롭 & 스마트 충돌 해결**
   * 패널 간(또는 외부 Windows 기본 탐색기와 양방향) 마우스 드래그 앤 드롭으로 파일/폴더 즉시 복사·이동
   * 동일 이름 충돌 시 **자동 번호 붙이기(`파일 (1).ext`)**, **덮어쓰기**, **건너뛰기** 및 *모두 적용* 옵션 제공
   * 우클릭 컨텍스트 메뉴에서 `[1~4번 창]으로 즉시 복사/이동`, `여기서 터미널 열기`, `기본 탐색기에서 열기` 지원
4. **확장자별 색상 하이라이트 필터 & 커스텀 편집기 (`🎨`)**
   * 폴더(골드 앰버), 실행/스크립트(에메랄드), 압축파일(퍼플), 이미지(스카이 블루), 문서(오렌지), 코드(라임), 미디어(핑크), 시스템(그레이) 자동 색상 구분 및 사용자 정의 색상/확장자 규칙 편집
5. **실시간 드라이브 용량 바 & 즐겨찾기 매니저 (`⭐`)**
   * 연결된 모든 로컬 디스크의 볼륨 레이블과 여유 공간/사용률(%) 툴팁 표시
   * 자주 쓰는 폴더 북마크 추가·삭제·순서 정렬
6. **트리플 엔진 아키텍처 & 작업 상태 자동 보존**
   * **Qt 엔진 (`PySide6` / `PyQt6` 자동 감지):** OS 네이티브 파일 아이콘, 외부 탐색기 드래그 앤 드롭, 다크/라이트 고해상도 테마 스타일시트(QSS)
   * **내장 폴백 엔진 (`Tkinter ttk`):** 외부 패키지를 설치할 수 없는 환경에서도 Python 표준 라이브러리만으로 100% 즉시 구동 (`python pyquaddir.py --tk`)
   * 종료 시 마지막 열린 탭 경로, 레이아웃, 다크/라이트 테마, 색상 규칙, 즐겨찾기 자동 저장 (`~/.pyquaddir_config.json`)

---

## ⌨️ 단축키 안내 (Keyboard Shortcuts)

| 단축키 | 동작 설명 |
| :--- | :--- |
| `Ctrl + 1` ~ `Ctrl + 6` | 4분할 / 2분할(좌우) / 2분할(상하) / 3분할(좌1우2) / 3분할(상1하2) / 1분할 전환 |
| `Ctrl + T` / `Ctrl + W` | 현재 활성 패널에 새 탭 열기 / 현재 탭 닫기 |
| `마우스 휠 클릭 (중간 버튼)` | 선택한 폴더를 새 탭으로 열기 |
| `Alt + Left` / `Alt + Right` | 활성 탭 이전 경로(뒤로) / 다음 경로(앞으로) 이동 |
| `Backspace` / `Alt + Up` | 상위 폴더(`..`)로 이동 |
| `Ctrl + C` / `Ctrl + X` / `Ctrl + V` | 선택 항목 복사 / 잘라내기(이동 대기) / 현재 폴더에 붙여넣기 |
| `Ctrl + Shift + N` | 현재 폴더에 새 폴더 만들기 |
| `F2` / `Delete` / `F5` | 이름 바꾸기 / 선택 항목 삭제 / 전체 패널 새로고침 |

---

## 🚀 빠른 실행 방법 (Quick Start)

### 1) 단일 실행 파일(`.exe`) 바로 다운로드 및 실행
Python 설치 없이 바로 실행하려면 [**GitHub Releases**](../../releases) 페이지에서 최신 `PyQuadDir.exe` 파일을 다운로드하여 실행하세요.
> **참고:** 개인 오픈소스 빌드 실행 파일이므로 Windows에서 최초 실행 시 *Windows의 PC 보호(SmartScreen)* 안내가 표시될 수 있습니다. **`추가 정보(More info)` → `실행(Run anyway)`**을 클릭하면 정상 실행됩니다.

### 2) Python 소스 코드로 직접 실행
```bash
# 저장소 클론
git clone https://github.com/shinjaehyun20/PyQuadDir.git
cd PyQuadDir

# (권장) Qt 고해상도 엔진 설치 (PySide6 또는 PyQt6)
pip install PySide6

# 실행
python pyquaddir.py

# 외부 패키지 설치 없이 순수 표준 라이브러리(Tkinter) 모드로 실행하려면:
python pyquaddir.py --tk
```

---

## 📦 단일 실행 파일(`PyQuadDir.exe`) 직접 빌드하기

에 포함된 `build_exe.py`를 실행하면 외부 그래픽 라이브러리(Pillow 등) 없이도 **순수 Python 바이너리 생성기**로 4분할 전용 아이콘(`pyquaddir.ico`)과 버전 리소스(`version_info.txt`)를 자동 생성한 뒤, `PyInstaller`로 깔끔한 단일 실행 파일(`dist/PyQuadDir.exe`)을 패키징합니다.

```bash
# 단일 실행 파일(dist/PyQuadDir.exe) 자동 빌드
python build_exe.py

# 빠른 초기 구동 속도를 위한 폴더형(--onedir) 빌드
python build_exe.py --onedir
```

---

## 📄 라이선스 (License)

본 프로젝트는 [**MIT License**](LICENSE) 하에 배포됩니다.
* 코드 내 Qt 바인딩은 LGPLv3 기반의 공식 `PySide6`와 `PyQt6`, 그리고 Python 내장 `Tkinter`를 모두 호환 지원합니다.
