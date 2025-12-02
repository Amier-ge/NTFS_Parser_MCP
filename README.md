# NTFS Parser MCP Server

NTFS 포렌식 파서를 MCP(Model Context Protocol) 서버로 제공

## 요구 사항

### 디렉토리 구조

이 MCP 서버는 `NTFS_Parser` 라이브러리에 의존합니다. **두 폴더가 반드시 같은 디렉토리 내에 위치해야 합니다.**

```
Parent_Directory/
├── NTFS_Parser/         ← 원본 NTFS 파서 라이브러리
│   ├── ntfs_parser.py
│   └── src/
│       ├── mft_parser.py
│       ├── usnjrnl_parser.py
│       ├── logfile_parser.py
│       └── ...
│
└── NTFS_Parser_MCP/     ← 이 MCP 서버
    ├── mcp_server.py
    └── ...
```

> ⚠️ `NTFS_Parser` 폴더가 없거나 다른 위치에 있으면 MCP 서버가 정상적으로 작동하지 않습니다.

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### MCP 서버 실행

```bash
python mcp_server.py
```

### 환경 세팅

```json
{
  "mcpServers": {
    "ntfs-parser": {
      "command": "[Python Path]",
      "args": [
        "[mcp_server.py Path]"
      ],
      "env": {
        "PYTHONPATH": "C:/Users/home/Desktop/Made_Tools/NTFS_Parser_MCP"
      }
    }
  }
}
```

## 제공 도구

| 도구 | 설명 |
|------|------|
| `parse_mft` | $MFT (Master File Table) 파싱 |
| `parse_usnjrnl` | $UsnJrnl:$J (USN Journal) 파싱 |
| `parse_logfile` | $LogFile (Transaction Log) 파싱 |
| `extract_from_image` | 디스크 이미지에서 아티팩트 추출 |
| `extract_and_analyze` | 추출 + 분석 한번에 |
| `analyze_artifacts` | 여러 아티팩트 통합 분석 |
| `get_info` | 도구 정보 조회 |

## 출력 형식

- CSV
- JSON
- SQLite

## 지원 이미지

- E01
- RAW

## 작성자

amier-ge