# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP 씬 청사진" width="900">
</p>

<p align="center"><strong>MCP를 통해 Godot 프로젝트를 검사하고, 편집하고, 실행하고, 디버깅합니다.</strong><br>AI 어시스턴트에서 씬, 스크립트, 실행 중인 게임을 다룰 수 있습니다.</p>

<p align="center"><a href="README.md">English</a> · 한국어</p>

<p align="center">
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
<a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 라이선스"></a>
</p>

## 시작하기

**Godot 4.7.2**와 로컬 stdio MCP 클라이언트가 필요합니다. Linux x86_64에서 검증했으며 다른 플랫폼의 네이티브 검증은 아직 수행하지 않았습니다.

### 1. 설치

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

질문 없이 최신 릴리스를 설치합니다. `godot-mcp` 명령은 새 터미널에서 사용할 수 있습니다.

### 2. AI 어시스턴트 연결

에이전트에게 다음 프롬프트를 전달하세요.

```text
Set up Godot MCP using this guide: https://github.com/smturtle2/godot-mcp/blob/main/docs/installation.md#agent-setup
```

### 3. 프로젝트 준비

Godot에서 프로젝트를 닫고, AI에게 프로젝트의 절대 경로를 알려 주며 플러그인 설치를 요청하세요. 설치 후 Godot에서 프로젝트를 열면 작업을 시작할 수 있습니다. 서버는 MCP 클라이언트가 자동으로 실행합니다.

터미널에서는 프로젝트 폴더에서 `godot-mcp init`을 실행해도 됩니다. 업데이트할 때는 연결된 Godot 프로젝트를 닫고 설치 스크립트를 다시 실행한 뒤 MCP를 다시 연결하세요.

## 참고

[44개 도구](docs/tools.md) · [설정 및 문제 해결](docs/installation.md) · [개발](docs/development.md) · [EUPL-1.2](LICENSE)
