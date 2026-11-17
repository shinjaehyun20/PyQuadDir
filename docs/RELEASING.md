# PyQuadDir 릴리스 관리

소스 푸시와 사용자용 릴리스는 별도로 확인한다. 이미 릴리스를 제공하는 이 저장소에서 커밋·푸시를 요청받으면 최신 릴리스의 버전·태그·파일도 함께 점검한다. 요청된 게시 범위에서 수행하며, 소스 푸시만 성공한 상태를 릴리스 발행으로 보고하지 않는다.

## 커밋·푸시할 때

1. 작업 트리와 원격 최신 상태를 확인하고 다른 작업자의 변경을 보존한다.
2. `pyquaddir.py`, `q_dir.py`, `build_exe.py`, `version_info.txt`, `README.md`, `CHANGELOG.md`의 버전과 실제 변경을 대조한다.
3. GitHub 최신 릴리스·태그·첨부 실행 파일의 버전을 확인한다. 배포할 기능·수정이 릴리스보다 앞서 있으면 새 버전의 릴리스를 함께 준비한다. 문서만 바뀌었으면 그 사실과 기존 실행 파일 유지 여부를 구분한다.
4. 검증·빌드·릴리스가 미완료라면 완료 상태와 남은 작업을 따로 보고한다. 릴리스가 게시된 뒤에는 배포된 파일을 같은 버전으로 조용히 교체하지 않는다. 바이트가 바뀌면 새 버전을 사용한다.

## 새 버전 발행

1. 변경 기록과 `docs/releases/vX.Y.Z.md`를 작성한다. 사용자에게 필요한 수정 사항, 호환성·제한, 설치 방법, 첨부 파일을 적는다.
2. 테스트와 GUI 자체 검사는 별도 프로필에서 실행한다. 사용자 설정·탭·즐겨찾기와 실행 중인 앱을 보존한다.
3. `python build_exe.py --system-msvc-runtime --no-open`으로 Windows x64 실행 파일을 빌드한다. 빌드가 끝나면 실제 파일 버전, GUI 자체 검사, PyInstaller 구성과 SHA-256을 확인한다.
4. 아래 배포 파일을 준비한다. 개인 설정·로그·이전 실행 파일·자격 증명은 포함하지 않는다.
   - `PyQuadDir.exe`: 사용자용 Windows x64 실행 파일.
   - `PyQuadDir-vX.Y.Z-Windows-x64.zip`: 실행 파일, 프로젝트 라이선스, 포함 구성 요소의 라이선스 고지, 설치 안내.
   - `PyQuadDir-vX.Y.Z-sources.zip`: 같은 버전의 앱 소스·빌드 안내와 포함된 제3자 구성 요소의 대응 소스 아카이브. 출처 URL·버전·SHA-256도 보존한다.
   - `SHA256SUMS.txt`: 공개하는 실행 파일과 ZIP의 실제 SHA-256.
5. 검증한 소스·문서를 커밋·푸시한 뒤 해당 커밋에 `vX.Y.Z` 태그를 만든다. 기존 태그를 이동하거나 강제로 덮어쓰지 않는다.
6. 태그와 릴리스 노트를 사용해 GitHub 릴리스를 만들고 배포 파일을 첨부한다. `latest` 지정은 실제 최신 정식 버전에만 적용한다.
7. 공개 릴리스 페이지에서 태그가 가리키는 커밋, 릴리스 노트, 자산 이름·크기·해시와 README 다운로드 링크를 확인한다. 원격 파일을 확인한 뒤에 발행 완료로 보고한다.

## Windows v3.2.0 빌드 기준

- CPython 3.11.9, Windows x64
- PyQt6 6.11.0, PyQt6-Qt6 6.11.2, PyQt6-sip 13.13.0
- PyInstaller 6.16.0
- Microsoft Visual C++ v14 x64 Runtime 14.44.35211.0 이상은 사용자 시스템에서 제공한다. 배포 파일은 Microsoft 런타임 DLL과 설치 프로그램을 포함하거나 자동 설치하지 않는다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install PyQt6==6.11.0 PyQt6-Qt6==6.11.2 PyQt6-sip==13.13.0 PyInstaller==6.16.0
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build_exe.py --system-msvc-runtime --no-open
$env:QT_QPA_PLATFORM = 'offscreen'
.\dist\PyQuadDir.exe --engine qt --self-test-gui --profile-dir .\test-profile
Get-FileHash .\dist\PyQuadDir.exe -Algorithm SHA256
```

이는 소스를 수정하고 다시 빌드하기 위한 기준이다. 빌드 시각·도구·운영체제 차이까지 고정한 비트 단위 동일 빌드는 검증하지 않았다. 제3자 라이브러리를 수정한 경우 해당 프로젝트 소스의 빌드 안내에 따라 라이브러리를 먼저 빌드·설치하고, 앱을 다시 패키징한다. 배포 ZIP의 라이선스와 소스 아카이브를 함께 유지한다.
