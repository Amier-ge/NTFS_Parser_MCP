import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Any

# 원본 NTFS_Parser 패키지 경로 추가
NTFS_PARSER_PATH = Path(__file__).parent.parent / "NTFS_Parser"
sys.path.insert(0, str(NTFS_PARSER_PATH))

from mcp.server.fastmcp import FastMCP

# MCP 서버 생성
mcp = FastMCP("ntfs-parser")

VERSION = "1.0.0"


@mcp.tool()
def parse_mft(
    input_path: str,
    output_path: str
) -> dict[str, Any]:

    from src.mft_parser import parse_mft_file, MFTParser

    if not Path(input_path).exists():
        return {"success": False, "error": f"Input file not found: {input_path}"}

    try:
        parser = MFTParser(input_path)
        total = parser.get_total_entries()

        start_time = datetime.now()

        parse_mft_file(
            input_path,
            output_path,
            include_deleted=True,
            output_format="json",
            include_path=True
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "total_entries": total,
            "elapsed_seconds": elapsed,
            "output_path": output_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def parse_usnjrnl(
    input_path: str,
    output_path: str
) -> dict[str, Any]:

    from src.usnjrnl_parser import parse_usnjrnl as _parse_usnjrnl

    if not Path(input_path).exists():
        return {"success": False, "error": f"Input file not found: {input_path}"}

    try:
        file_size = Path(input_path).stat().st_size
        start_time = datetime.now()

        _parse_usnjrnl(
            input_path,
            output_path,
            mft_path=None,
            output_format="json",
            include_path=False
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "file_size_mb": file_size / (1024 * 1024),
            "elapsed_seconds": elapsed,
            "output_path": output_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def parse_logfile(
    input_path: str,
    output_path: str
) -> dict[str, Any]:

    from src.logfile_parser import parse_logfile as _parse_logfile

    if not Path(input_path).exists():
        return {"success": False, "error": f"Input file not found: {input_path}"}

    try:
        start_time = datetime.now()

        _parse_logfile(input_path, output_path, output_format="json")

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "elapsed_seconds": elapsed,
            "output_path": output_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def extract_from_image(
    input_path: str,
    output_path: str
) -> dict[str, Any]:

    from src.image_handler import ImageHandler, find_ntfs_partitions, NTFSExtractor

    if not Path(input_path).exists():
        return {"success": False, "error": f"Image file not found: {input_path}"}

    try:
        Path(output_path).mkdir(parents=True, exist_ok=True)

        results = {"success": True, "partitions": []}

        with ImageHandler(input_path) as image:
            partitions = find_ntfs_partitions(image)
            partitions_to_process = list(enumerate(partitions))

            for i, part in partitions_to_process:
                part_result = {
                    "partition": i,
                    "offset": part.offset,
                    "cluster_size": part.cluster_size,
                    "extracted": {}
                }

                extractor = NTFSExtractor(part)

                # MFT
                mft_path = Path(output_path) / f"partition{i}_MFT"
                if extractor.extract_mft(str(mft_path)):
                    part_result["extracted"]["mft"] = str(mft_path)

                # LogFile
                logfile_path = Path(output_path) / f"partition{i}_LogFile"
                if extractor.extract_logfile(str(logfile_path)):
                    part_result["extracted"]["logfile"] = str(logfile_path)

                # UsnJrnl
                usnjrnl_path = Path(output_path) / f"partition{i}_UsnJrnl_J"
                if extractor.extract_usnjrnl(str(usnjrnl_path), verbose=False):
                    part_result["extracted"]["usnjrnl"] = str(usnjrnl_path)

                results["partitions"].append(part_result)

        results["total_partitions"] = len(partitions)
        return results

    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}. For E01 support, install: pip install pyewf-python"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def extract_and_analyze(input_path: str, output_path: str) -> dict[str, Any]:

    import json
    import tempfile
    from src.image_handler import ImageHandler, find_ntfs_partitions, NTFSExtractor
    from src.mft_parser import parse_mft_file
    from src.usnjrnl_parser import parse_usnjrnl
    from src.logfile_parser import parse_logfile as _parse_logfile

    if not Path(input_path).exists():
        return {"success": False, "output_path": output_path}

    try:
        start_time = datetime.now()
        Path(output_path).mkdir(parents=True, exist_ok=True)

        results = {"partitions": []}

        with ImageHandler(input_path) as image:
            partitions = find_ntfs_partitions(image)

            for i, part in enumerate(partitions):
                part_result = {
                    "partition": i,
                    "offset": part.offset,
                    "cluster_size": part.cluster_size,
                    "output_files": {}
                }

                extractor = NTFSExtractor(part)

                partition_info = {
                    "partition_index": i,
                    "offset": part.offset,
                    "cluster_size": part.cluster_size
                }

                # MFT 데이터 (별도 파일)
                mft_data = {
                    "partition_info": partition_info,
                    "MFT": []
                }

                # Journal 데이터 (UsnJrnl + LogFile 통합, 별도 파일)
                journal_data = {
                    "partition_info": partition_info,
                    "UsnJrnl": [],
                    "LogFile": []
                }

                # 임시 디렉토리 사용
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # MFT 추출 및 파싱
                    mft_raw = temp_path / "MFT"
                    mft_json = temp_path / "MFT.json"
                    if extractor.extract_mft(str(mft_raw)):
                        try:
                            parse_mft_file(str(mft_raw), str(mft_json), include_deleted=True, output_format="json", include_path=True)
                            with open(mft_json, "r", encoding="utf-8") as f:
                                mft_data["MFT"] = json.load(f)
                        except Exception as e:
                            mft_data["MFT"] = {"error": str(e)}

                    # LogFile 추출 및 파싱
                    logfile_raw = temp_path / "LogFile"
                    logfile_json = temp_path / "LogFile.json"
                    if extractor.extract_logfile(str(logfile_raw)):
                        try:
                            _parse_logfile(str(logfile_raw), str(logfile_json), output_format="json")
                            with open(logfile_json, "r", encoding="utf-8") as f:
                                journal_data["LogFile"] = json.load(f)
                        except Exception as e:
                            journal_data["LogFile"] = {"error": str(e)}

                    # UsnJrnl 추출 및 파싱
                    usnjrnl_raw = temp_path / "UsnJrnl_J"
                    usnjrnl_json = temp_path / "UsnJrnl.json"
                    if extractor.extract_usnjrnl(str(usnjrnl_raw), verbose=False):
                        try:
                            parse_usnjrnl(str(usnjrnl_raw), str(usnjrnl_json), mft_path=None, output_format="json", include_path=False)
                            with open(usnjrnl_json, "r", encoding="utf-8") as f:
                                journal_data["UsnJrnl"] = json.load(f)
                        except Exception as e:
                            journal_data["UsnJrnl"] = {"error": str(e)}

                # MFT JSON 파일 저장
                mft_json_path = Path(output_path) / f"partition{i}_mft.json"
                with open(mft_json_path, "w", encoding="utf-8") as f:
                    json.dump(mft_data, f, ensure_ascii=False, indent=2)
                part_result["output_files"]["mft"] = str(mft_json_path)

                # Journal (UsnJrnl + LogFile) JSON 파일 저장
                journal_json_path = Path(output_path) / f"partition{i}_journal.json"
                with open(journal_json_path, "w", encoding="utf-8") as f:
                    json.dump(journal_data, f, ensure_ascii=False, indent=2)
                part_result["output_files"]["journal"] = str(journal_json_path)

                results["partitions"].append(part_result)

        results["elapsed_seconds"] = (datetime.now() - start_time).total_seconds()
        results["total_partitions"] = len(results["partitions"])
        results["input_path"] = input_path
        results["output_path"] = output_path

        return {"success": True, "output_path": output_path}

    except ImportError as e:
        return {"success": False, "output_path": output_path}
    except Exception as e:
        return {"success": False, "output_path": output_path}


@mcp.tool()
def search_keyword(
    json_path: str,
    keyword: str
) -> dict[str, Any]:

    import json

    if not Path(json_path).exists():
        return {"success": False, "error": f"JSON file not found: {json_path}"}

    def contains_keyword(obj: Any, keyword: str) -> bool:
        if isinstance(obj, str):
            return keyword.lower() in obj.lower()
        elif isinstance(obj, dict):
            return any(contains_keyword(v, keyword) for v in obj.values())
        elif isinstance(obj, list):
            return any(contains_keyword(item, keyword) for item in obj)
        return False

    try:
        start_time = datetime.now()

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        matches = []

        if isinstance(data, list):
            for record in data:
                if contains_keyword(record, keyword):
                    matches.append(record)
        elif isinstance(data, dict):
            for key in ["UsnJrnl", "LogFile", "MFT"]:
                if key in data and isinstance(data[key], list):
                    for record in data[key]:
                        if contains_keyword(record, keyword):
                            matches.append(record)

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "keyword": keyword,
            "json_path": json_path,
            "total_matches": len(matches),
            "elapsed_seconds": elapsed,
            "matches": matches
        }

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON file: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_info() -> dict[str, Any]:

    return {
        "name": "NTFS Forensic Parser",
        "version": VERSION,
        "author": "amier-ge",
        "description": "MFT / LogFile / UsnJrnl:$J Analysis Tool",
        "capabilities": [
            "parse_mft - Parse $MFT (Master File Table)",
            "parse_usnjrnl - Parse $UsnJrnl:$J (USN Journal)",
            "parse_logfile - Parse $LogFile (Transaction Log)",
            "extract_from_image - Extract artifacts from E01/RAW disk images",
            "extract_and_analyze - One-step extraction and analysis",
            "search_keyword - Search keyword in parsed JSON files"
        ],
        "supported_formats": ["csv", "json", "sqlite"],
        "supported_images": ["E01", "RAW"],
        "timezone": "UTC+9 (KST)"
    }


if __name__ == "__main__":
    mcp.run()
