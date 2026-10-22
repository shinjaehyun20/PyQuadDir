# PyQuadDir v2.0 — Quad-View Multi-Tab Desktop File Explorer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: v2.0.0](https://img.shields.io/badge/Release-v2.0.0-emerald.svg)](../../releases)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Platform: Windows / Cross-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6.svg)](#)

**PyQuadDir**는 Windows 로컬 드라이브(`C:\`, `D:\` 등)와 파일 시스템을 한눈에 제어하는 **4분할(Quad-View) 다중 탭 데스크톱 파일 탐색기**입니다.

> *Inspired by the classic quad-pane file manager concept (such as Q-Dir), cleanly implemented from scratch in pure Python with a Triple-Engine architecture (`PySide6` / `PyQt6` / `Tkinter`).*

---

## 🆕 v2.0 주요 업데이트 (What's New in v2.0)

1. **Windows 11 탐색기 스타일 통합 명령 바 & 상단 바 컴팩트화**
   * `[⊕ 새로 만들기 ▾]` (폴더, `.txt`, `.md`, `.py`, `.bat` 즉시 생성) | `[✂️ 잘라내기]` `[📋 복사]` `[📥 붙여넣기]` `[✏️ 이름 바꾸기]` `[📤 다른 패널로 전송 ▾]` `[🗑️ 삭제]`
   * `[📐 레이아웃 ▾]` 및 `[💽 드라이브 ▾]`를 드롭다운 메뉴로 통합하여 **2층 즐겨찾기(`⭐`) 전용 바의 가로 수납 공간을 대폭 확장**했습니다.
2. **8가지 보기 모드(`⊞ 보기 ▾`) & 실제 이미지 썸네일(Thumbnail) 캐시 렌더링**
   * `아주 큰 아이콘(144px)`, `큰 아이콘(88px)`, `보통 아이콘(56px)`, `작은 아이콘(28px)`, `목록`, `자세히`, `타일`, `내용` 8가지 뷰 모드 전환 및 **4개 패널 일괄 적용** 지원
   * 이미지 파일(`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`, `.svg`, `.ico`, `.tif`)의 실제 사진 썸네일을 고속 인메모리 캐시로 즉시 렌더링
   * 아이콘/썸네일 표시 토글, 파일 확장명 표시 토글, 숨긴 항목 표시 토글 지원
3. **고급 정렬 및 그룹화(`⇅ 정렬 ▾`)**
   * `이름`, `수정한 날짜`, `유형`, `크기`, `확장자`, `만든 날짜` 기준 오름차순/내림차순 정렬
   * **분류 방법(그룹화):** `유형별`, `수정한 날짜별(오늘/어제/이번 주/이전)`, `크기별(대용량/중간/소형)` 섹션 헤더 그룹핑 지원
4. **우측 `[◧ 미리 보기]` & `[◨ 세부 정보]` 인스펙터 사이드 패널**
   * 파일 선택 시 우측 사이드 패널에서 **고해상도 이미지 프리뷰(해상도 픽셀 표시)** 및 **소스 코드/텍스트/마크다운/로그 파일 내용 실시간 미리보기** 제공
5. **`Ctrl + A` 전체 선택 시 상위 폴더(`..`) 자동 제외 보호**
   * `Ctrl + A` 또는 마우스 드래그 다중 선택 시 `📁 .. (상위 폴더)` 항목이 선택 목록에서 자동 제외되어 실수로 상위 폴더가 작업 대상에 포함되는 것을 방지합니다.

---

## ✨ 핵심 기능 (Core Features)

* **6가지 화면 분할 레이아웃 실시간 전환 (`Ctrl+1` ~ `Ctrl+6`)**: `4분할(2×2)`, `2분할(좌/우)`, `2분할(상/하)`, `3분할(좌1·우2)`, `3분할(상1·하2)`, `1분할(단일 최대화)` 및 `⚖️ 분할 창 비율 균등 정렬`
* **패널별 독립 다중 탭(Multi-Tab) 탐색**: 새 탭(`Ctrl+T`), 탭 닫기(`Ctrl+W`), 폴더 **마우스 휠 클릭**으로 새 탭 열기, 패널별 히스토리 및 실시간 키워드 필터(`🔍`)
* **창 간 드래그 앤 드롭 & 스마트 이름 충돌 해결**: 덮어쓰기 / 자동 번호 붙이기(`파일 (1).ext`) / 건너뛰기 및 *다음 충돌 항목에 모두 적용* 체크박스 지원
* **확장자별 색상 하이라이트 필터 & 커스텀 편집기 (`🎨`)**: 8대 파일 카테고리별 다크/라이트 테마 맞춤 색상 하이라이트 및 사용자 규칙 편집
* **트리플 엔진 아키텍처 (`PySide6` / `PyQt6` / `Tkinter`)**: Qt 엔진 미설치 환경에서도 표준 라이브러리 `Tkinter` 폴백(`--tk`)으로 즉시 구동

---

## ⌨️ 단축키 안내 (Keyboard Shortcuts)

| 단축키 | 동작 설명 |
| :--- | :--- |
| `Ctrl + 1` ~ `Ctrl + 6` | 4분할 / 2분할(좌우) / 2분할(상하) / 3분할(좌1우2) / 3분할(상1하2) / 1분할 전환 |
| `Ctrl + T` / `Ctrl + W` | 현재 활성 패널에 새 탭 열기 / 현재 탭 닫기 |
| `Ctrl + A` | 상위 폴더(`..`)를 제외한 현재 폴더 내 모든 파일/폴더 전체 선택 |
| `마우스 휠 클릭 (중간 버튼)` | 선택한 폴더를 새 탭으로 열기 |
| `Alt + Left` / `Alt + Right` | 활성 탭 이전 경로(뒤로) / 다음 경로(앞으로) 이동 |
| `Backspace` / `Alt + Up` | 상위 폴더(`..`)로 이동 |
| `Ctrl + C` / `Ctrl + X` / `Ctrl + V` | 선택 항목 복사 / 잘라내기(이동 대기) / 현재 폴더에 붙여넣기 |
| `Ctrl + Shift + N` | 현재 폴더에 새 폴더 만들기 |
| `F2` / `Delete` / `F5` | 이름 바꾸기 / 선택 항목 삭제 / 전체 패널 새로고침 |

---

## 🚀 빠른 실행 방법 (Quick Start)

### 1) 단일 실행 파일(`.exe`) 바로 다운로드 및 실행
Python 설치 없이 바로 실행하려면 [**GitHub Releases**](../../releases) 페이지에서 최신 `PyQuadDir.exe` (v2.0.0) 파일을 다운로드하여 실행하세요.
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

```bash
# 단일 실행 파일(dist/PyQuadDir.exe) 자동 빌드
python build_exe.py

# 빠른 초기 구동 속도를 위한 폴더형(--onedir) 빌드
python build_exe.py --onedir
```

---

## 📄 라이선스 (License)

본 프로젝트는 [**MIT License**](LICENSE) 하에 배포됩니다.
