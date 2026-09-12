# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP 씬 청사진" width="900">
</p>

<p align="center"><strong>MCP를 통해 Godot 프로젝트를 살펴보고, 편집하고, 실행하고, 디버깅합니다.</strong><br>AI 어시스턴트에서 씬, 스크립트, 실행 중인 게임을 다룰 수 있습니다.</p>

<p align="center"><a href="README.md">English</a> · 한국어</p>

<p align="center">
<a href="https://github.com/smturtle2/godot-mcp/releases/latest"><img src="https://img.shields.io/github/v/release/smturtle2/godot-mcp" alt="최신 릴리스"></a>
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
<a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 라이선스"></a>
</p>

## 할 수 있는 일

- 저장하지 않은 에디터 내용까지 포함해 현재 씬, 노드, 스크립트, 리소스, 시그널을 편집할 수 있습니다.
- 애니메이션, 애니메이션 그래프, TileSet, 타일 맵을 만들고 프로젝트 설정과 입력 동작을 구성할 수 있습니다.
- 게임을 실행하고 입력을 보내며, 게임 화면이나 에디터 창을 캡처하고, GDScript 디버깅 상태를 확인하고, 성능을 측정할 수 있습니다.
- 에셋을 가져오고, 참조 관계를 고려해 이동·삭제할 수 있습니다. 복구 가능한 삭제를 지원하며 프로젝트 프리셋으로 빌드를 내보낼 수 있습니다.

서버는 `get_guide`를 통해 기능, Godot 개발 선택지, 에디터 개념, 작업 예시, 복구, 도구 선택을 다루는 영어 매뉴얼을 제공합니다. 에디터에 연결하기 전에도 에이전트가 MCP를 통해 이 매뉴얼을 읽을 수 있습니다.

## 시작하기

**Godot 4.7.2**와 로컬 stdio MCP 클라이언트가 필요합니다. Linux x86_64에서 테스트했으며 다른 네이티브 플랫폼은 아직 검증하지 않았습니다.

### 1. 설치

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

질문 없이 최신 릴리스를 설치하고 필요한 Python 런타임을 관리합니다. `godot-mcp`를 사용하려면 새 터미널을 여세요.

### 2. AI 어시스턴트 연결

에이전트에게 다음 프롬프트를 전달하세요.

```text
Set up Godot MCP using this guide: https://github.com/smturtle2/godot-mcp/blob/main/src/godot_mcp/guide_content/start.md#connect-the-mcp-client
```

클라이언트는 런처의 절대 경로와 `connect` 인수로 서버를 시작합니다. 플랫폼별 경로는 [연결 가이드](src/godot_mcp/guide_content/start.md#connect-the-mcp-client)를 참고하세요.

### 3. 프로젝트 준비

Godot에서 기존 프로젝트를 닫고 에이전트에게 프로젝트의 절대 경로를 전달해 `install_plugin`으로 플러그인을 설치해 달라고 요청하세요. 그런 다음 Godot에서 프로젝트를 여세요. 에이전트는 `get_context`로 프로젝트를 살펴보거나 여러 개의 열린 프로젝트 중에서 선택할 수 있습니다.

터미널에서는 프로젝트 폴더에서 `godot-mcp init`을 실행해도 됩니다. 업데이트할 때는 연결된 Godot 프로젝트를 닫고 설치 스크립트를 다시 실행한 뒤 MCP를 다시 연결하세요.

## 에이전트와 작업하기

변경할 내용이나 문제를 일상적인 말로 설명하세요. 서버 지침은 관련 사용법과 개발 지침을 확인하도록 에이전트를 `get_guide`로 안내합니다. 개발 섹션은 특정 게임 스타일이나 프로젝트 아키텍처를 강요하지 않고 Godot의 기술적 선택지를 설명합니다.

편집에는 현재 에디터 상태가 사용됩니다. 소스 변경은 기본적으로 저장되지 않으며, 저장과 소스 진단은 별도 작업입니다. 진행 중인 작업은 변경을 반복하지 않고 상태를 확인할 수 있습니다. 에디터 실행 취소와 복구 가능한 에셋 삭제는 서로 다른 보존 규칙을 따르며, 자세한 내용은 [사용 예시](src/godot_mcp/guide_content/work.md)와 [복구 가이드](src/godot_mcp/guide_content/recovery.md)에 설명되어 있습니다.

## 참고

[설정](src/godot_mcp/guide_content/start.md) · [Godot 개발](src/godot_mcp/guide_content/development.md) · [에디터 개념](src/godot_mcp/guide_content/model.md) · [사용법](src/godot_mcp/guide_content/work.md) · [복구](src/godot_mcp/guide_content/recovery.md) · [49개 도구](docs/tools.md)

[기여 및 서버 개발](docs/development.md) · [변경 기록](CHANGELOG.md) · [EUPL-1.2](LICENSE)
