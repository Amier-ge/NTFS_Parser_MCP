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
    output_path: str,
    output_format: str = "csv",
    active_only: bool = False,
    include_path: bool = True
) -> dict[str, Any]:

    from src.mft_parser import parse_mft_file, MFTParser

    if not Path(input_path).exists():
        return {"success": False, "error": f"Input file not found: {input_path}"}

    if output_format not in ["csv", "json", "sqlite"]:
        return {"success": False, "error": f"Invalid format: {output_format}. Use csv, json, or sqlite"}

    try:
        parser = MFTParser(input_path)
        total = parser.get_total_entries()

        start_time = datetime.now()

        parse_mft_file(
            input_path,
            output_path,
            include_deleted=not active_only,
            output_format=output_format,
            include_path=include_path
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "total_entries": total,
            "elapsed_seconds": elapsed,
            "output_path": output_path,
            "format": output_format
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def parse_usnjrnl(
    input_path: str,
    output_path: str,
    output_format: str = "csv",
    mft_path: str | None = None
) -> dict[str, Any]:
    """
    Parse NTFS $UsnJrnl:$J (USN Journal) file.

    Args:
        input_path: Path to the $UsnJrnl:$J file
        output_path: Output file path for results
        output_format: Output format - csv, json, or sqlite (default: csv)
        mft_path: Optional path to $MFT file for full path resolution

    Returns:
        Dictionary with parsing results including record count and elapsed time
    """
    from src.usnjrnl_parser import parse_usnjrnl as _parse_usnjrnl

    if not Path(input_path).exists():
        return {"success": False, "error": f"Input file not found: {input_path}"}

    if mft_path and not Path(mft_path).exists():
        return {"success": False, "error": f"MFT file not found: {mft_path}"}

    if output_format not in ["csv", "json", "sqlite"]:
        return {"success": False, "error": f"Invalid format: {output_format}. Use csv, json, or sqlite"}

    try:
        file_size = Path(input_path).stat().st_size
        start_time = datetime.now()

        _parse_usnjrnl(
            input_path,
            output_path,
            mft_path=mft_path,
            output_format=output_format,
            include_path=bool(mft_path)
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "file_size_mb": file_size / (1024 * 1024),
            "elapsed_seconds": elapsed,
            "output_path": output_path,
            "format": output_format,
            "path_resolution": bool(mft_path)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def parse_logfile(
    input_path: str,
    output_path: str,
    output_format: str = "csv"
) -> dict[str, Any]:

    from src.logfile_parser import parse_logfile as _parse_logfile

    if not Path(input_path).exists():
        return {"success": False, "error": f"Input file not found: {input_path}"}

    if output_format not in ["csv", "json"]:
        return {"success": False, "error": f"Invalid format: {output_format}. LogFile supports csv or json only"}

    try:
        start_time = datetime.now()

        _parse_logfile(input_path, output_path, output_format=output_format)

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "elapsed_seconds": elapsed,
            "output_path": output_path,
            "format": output_format
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def extract_from_image(
    image_path: str,
    output_dir: str,
    partition: int | None = None,
    verbose: bool = False
) -> dict[str, Any]:

    from src.image_handler import ImageHandler, find_ntfs_partitions, NTFSExtractor

    if not Path(image_path).exists():
        return {"success": False, "error": f"Image file not found: {image_path}"}

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        results = {"success": True, "partitions": []}

        with ImageHandler(image_path) as image:
            partitions = find_ntfs_partitions(image)

            if partition is not None:
                if partition < 0 or partition >= len(partitions):
                    return {"success": False, "error": f"Invalid partition: {partition} (valid: 0-{len(partitions)-1})"}
                partitions_to_process = [(partition, partitions[partition])]
            else:
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
                mft_path = Path(output_dir) / f"partition{i}_MFT"
                if extractor.extract_mft(str(mft_path)):
                    part_result["extracted"]["mft"] = str(mft_path)

                # LogFile
                logfile_path = Path(output_dir) / f"partition{i}_LogFile"
                if extractor.extract_logfile(str(logfile_path)):
                    part_result["extracted"]["logfile"] = str(logfile_path)

                # UsnJrnl
                usnjrnl_path = Path(output_dir) / f"partition{i}_UsnJrnl_J"
                if extractor.extract_usnjrnl(str(usnjrnl_path), verbose=verbose):
                    part_result["extracted"]["usnjrnl"] = str(usnjrnl_path)

                results["partitions"].append(part_result)

        results["total_partitions"] = len(partitions)
        return results

    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}. For E01 support, install: pip install pyewf-python"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def extract_and_analyze(
    image_path: str,
    output_dir: str,
    output_format: str = "sqlite",
    partition: int | None = None,
    skip_mft: bool = False,
    skip_usnjrnl: bool = False,
    skip_logfile: bool = False,
    keep_temp: bool = False
) -> dict[str, Any]:

    from src.image_handler import ImageHandler, find_ntfs_partitions, NTFSExtractor
    from src.mft_parser import parse_mft_file
    from src.usnjrnl_parser import parse_usnjrnl as _parse_usnjrnl
    from src.logfile_parser import parse_logfile as _parse_logfile

    if not Path(image_path).exists():
        return {"success": False, "error": f"Image file not found: {image_path}"}

    if output_format not in ["csv", "json", "sqlite"]:
        return {"success": False, "error": f"Invalid format: {output_format}"}

    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        temp_dir = output_path / "temp_extracted"
        temp_dir.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now()
        results = {"success": True, "partitions": []}

        with ImageHandler(image_path) as image:
            partitions = find_ntfs_partitions(image)

            if partition is not None:
                if partition < 0 or partition >= len(partitions):
                    return {"success": False, "error": f"Invalid partition: {partition}"}
                partitions_to_process = [(partition, partitions[partition])]
            else:
                partitions_to_process = list(enumerate(partitions))

            ext = '.db' if output_format == 'sqlite' else f'.{output_format}'

            for i, part in partitions_to_process:
                part_result = {"partition": i, "analyzed": {}}
                extractor = NTFSExtractor(part)

                mft_temp_path = temp_dir / f"partition{i}_MFT"

                # MFT
                if not skip_mft:
                    mft_output = output_path / f"partition{i}_MFT{ext}"
                    if extractor.extract_mft(str(mft_temp_path)):
                        try:
                            parse_mft_file(
                                str(mft_temp_path),
                                str(mft_output),
                                include_deleted=True,
                                output_format=output_format,
                                include_path=True
                            )
                            part_result["analyzed"]["mft"] = str(mft_output)
                        except Exception as e:
                            part_result["analyzed"]["mft_error"] = str(e)

                # UsnJrnl
                if not skip_usnjrnl:
                    usnjrnl_temp = temp_dir / f"partition{i}_UsnJrnl_J"
                    usnjrnl_output = output_path / f"partition{i}_UsnJrnl{ext}"
                    if extractor.extract_usnjrnl(str(usnjrnl_temp)):
                        try:
                            mft_for_path = str(mft_temp_path) if (not skip_mft and mft_temp_path.exists()) else None
                            _parse_usnjrnl(
                                str(usnjrnl_temp),
                                str(usnjrnl_output),
                                mft_path=mft_for_path,
                                output_format=output_format,
                                include_path=bool(mft_for_path)
                            )
                            part_result["analyzed"]["usnjrnl"] = str(usnjrnl_output)
                        except Exception as e:
                            part_result["analyzed"]["usnjrnl_error"] = str(e)

                # LogFile
                if not skip_logfile:
                    logfile_temp = temp_dir / f"partition{i}_LogFile"
                    logfile_format = output_format if output_format != 'sqlite' else 'csv'
                    logfile_ext = '.csv' if output_format == 'sqlite' else ext
                    logfile_output = output_path / f"partition{i}_LogFile{logfile_ext}"
                    if extractor.extract_logfile(str(logfile_temp)):
                        try:
                            _parse_logfile(str(logfile_temp), str(logfile_output), output_format=logfile_format)
                            part_result["analyzed"]["logfile"] = str(logfile_output)
                        except Exception as e:
                            part_result["analyzed"]["logfile_error"] = str(e)

                results["partitions"].append(part_result)

        # 임시 파일 정리
        if not keep_temp:
            import shutil
            try:
                shutil.rmtree(temp_dir)
                results["temp_cleaned"] = True
            except Exception:
                results["temp_cleaned"] = False

        elapsed = (datetime.now() - start_time).total_seconds()
        results["elapsed_seconds"] = elapsed
        results["output_dir"] = str(output_path)

        return results

    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def analyze_artifacts(
    output_dir: str,
    output_format: str = "csv",
    mft_path: str | None = None,
    usnjrnl_path: str | None = None,
    logfile_path: str | None = None
) -> dict[str, Any]:

    from src.analyzer import UnifiedAnalyzer

    if not any([mft_path, usnjrnl_path, logfile_path]):
        return {"success": False, "error": "At least one input file required (mft_path, usnjrnl_path, or logfile_path)"}

    # 파일 존재 확인
    for path, name in [(mft_path, "MFT"), (usnjrnl_path, "UsnJrnl"), (logfile_path, "LogFile")]:
        if path and not Path(path).exists():
            return {"success": False, "error": f"{name} file not found: {path}"}

    if output_format not in ["csv", "json", "sqlite"]:
        return {"success": False, "error": f"Invalid format: {output_format}"}

    try:
        start_time = datetime.now()

        analyzer = UnifiedAnalyzer(output_dir)
        result_path = analyzer.analyze_all(
            mft_path=mft_path,
            logfile_path=logfile_path,
            usnjrnl_path=usnjrnl_path,
            output_format=output_format
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "elapsed_seconds": elapsed,
            "output_path": result_path,
            "format": output_format,
            "inputs": {
                "mft": mft_path,
                "usnjrnl": usnjrnl_path,
                "logfile": logfile_path
            }
        }
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
            "analyze_artifacts - Unified analysis of multiple artifacts"
        ],
        "supported_formats": ["csv", "json", "sqlite"],
        "supported_images": ["E01", "RAW"],
        "timezone": "UTC+9 (KST)"
    }


if __name__ == "__main__":
    mcp.run()
