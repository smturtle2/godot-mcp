# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP 씬 청사진" width="900">
</p>

<p align="center"><strong>MCP를 통해 Godot 프로젝트를 검사하고, 편집하고, 실행하고, 디버깅합니다.</strong><br>
AI 어시스턴트에서 씬, 스크립트, 실행 중인 게임을 다룰 수 있습니다.</p>

<p align="center">
  <a href="README.md">English</a> · 한국어
</p>

<p align="center">
  <a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
  <a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
  <a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 라이선스"></a>
</p>

## 시작하기

Godot **4.7.2**와 로컬 stdio 서버를 지원하는 MCP 클라이언트가 필요합니다. Linux x86_64에서 테스트했으며 macOS, Windows, Linux ARM64의 네이티브 테스트는 아직 수행하지 않았습니다.

### 최신 릴리스 설치

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

공개 설치 스크립트는 최신 안정 릴리스를 가져옵니다. Godot 실행 파일이나 엔진 버전을 탐지하거나 입력받지 않습니다. 사용자 로컬에 고정된 `godot-mcp` 명령을 설치하고 사용자 셸 `PATH`에 디렉터리를 추가하므로, 설치 후 새 터미널을 열어야 합니다.

설치 프로그램은 MCP 클라이언트 설정에 사용할 고정 절대 경로 stdio 명령을 출력합니다. GUI MCP 클라이언트는 셸과 `PATH`가 다를 수 있으므로 출력된 명령을 사용해야 합니다. 서버 프로세스는 클라이언트가 실행하며, 설치 프로그램은 클라이언트 설정을 수정하지 않습니다.

### AI로 프로젝트 플러그인 설치

출력된 stdio 명령을 MCP 클라이언트에 등록한 뒤, AI 어시스턴트에게 절대 경로의 프로젝트 디렉터리에 플러그인을 설치해 달라고 요청하세요. `install_plugin` 도구가 프로젝트에 플러그인을 설치하고 활성화합니다. Godot를 열기 전에도 실행할 수 있습니다.

설치할 프로젝트는 Godot에서 닫아 두세요. 설치가 끝나면 Godot에서 프로젝트를 열면 됩니다. 그런 다음 AI에게 다음과 같이 요청할 수 있습니다.

> 연결된 Godot 프로젝트를 확인하고 현재 씬을 설명해 줘.

여러 프로젝트가 열려 있으면 선택할 프로젝트의 절대 경로를 알려 주세요.

### CLI 대안

```bash
godot-mcp init /path/to/project
```

`godot-mcp init`에 프로젝트 경로를 생략하면 현재 폴더를 사용합니다. 실행 중인 에디터와의 연결은 다음 명령으로 확인할 수 있습니다.

```bash
godot-mcp check --project /path/to/project
```

업데이트 후에도 명령과 MCP 실행 경로는 그대로 유지됩니다. 연결된 Godot 프로젝트를 닫고 설치 스크립트를 다시 실행한 다음, MCP를 다시 연결하면 새 서버로 시작합니다.

프로젝트 연결, 검색, 업데이트, 롤백은 [설정 및 문제 해결](docs/installation.md)을 참고하세요.

## 도구

총 **43개 도구**가 있습니다. 42개 편집기/런타임 도구와 `install_plugin` 설정 도구로 구성됩니다. 씬, 스크립트, 리소스, 애니메이션, TileMap, 게임 입력, 디버깅, 내보내기를 지원합니다. 저장하기 전에 변경 사항을 검사할 수 있으며, 런타임 도구는 실행 중인 게임의 실제 관찰 결과를 반환합니다.

전체 도구의 설명과 입력 스키마는 [도구 레퍼런스](docs/tools.md)에서 확인할 수 있습니다.

## 개발

설정, 테스트, 릴리스는 [개발 가이드](docs/development.md), 서버와 Godot 플러그인 구조는 [아키텍처](docs/architecture.md)를 참고하세요.

## 라이선스

[EUPL-1.2](LICENSE)
