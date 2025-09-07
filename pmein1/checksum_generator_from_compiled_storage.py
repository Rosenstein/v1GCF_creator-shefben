#!/usr/bin/env python
# encoding: ascii or latin-1, Python 3.9.13 assumed

import sys
import os
import struct
import pickle
import zlib

##############################################################################
# This script:
#  1) Loads the <app_id>_<app_version>.index (pickle) to find offsets & lengths.
#  2) Reads <app_id>_<app_version>.dat into memory.
#  3) For each file_id in the index, splits the file data into 32 KB chunks
#     (0x8000 bytes), generating one checksum per chunk with adler32(0, data).
#  4) Fills in missing file IDs from 0..maxID with zero checksums ( (0,0) entry ).
#  5) Produces <app_id>_<app_version>.checksums with the same structure your
#     generator script uses:
#       format_code=0x14893721, dummy0=0, fileIdCount, checksumCount
#       (fileIdCount * [chunkCount, firstChecksumIndex])
#       (checksumCount * [4-byte checksums])
#
# So you get exactly ONE CHECKSUM PER 32KB CHUNK of data, for each file.
##############################################################################

CHUNK_SIZE = 0x8000  # 32 KB

def adler_crc32(data_block: bytes) -> int:
    """
    Exactly one 32-bit adler32(0, data_block) per chunk.
    """
    return zlib.adler32(data_block) & 0xFFFFFFFF

def generate_32kb_checksums(app_id: str, app_version: str):
    """
    1) Read <app_id>_<app_version>.index
    2) Read <app_id>_<app_version>.dat
    3) Compute chunk-based checksums (32 KB each) for all file IDs
    4) Write <app_id>_<app_version>.checksums
    """

    index_file = f"{app_id}_{app_version}.index"
    dat_file   = f"{app_id}_{app_version}.dat"
    checksums_file = f"{app_id}_{app_version}.checksums"

    if not os.path.isfile(index_file):
        print(f"Error: Missing index file: {index_file}")
        sys.exit(1)
    if not os.path.isfile(dat_file):
        print(f"Error: Missing dat file: {dat_file}")
        sys.exit(1)

    # 1) Load index data
    with open(index_file, "rb") as f_idx:
        index_data = pickle.load(f_idx)
    # index_data is something like:
    # {1: {'offset':0, 'length':100}, 2: {...}, ... }

    if not index_data:
        # no files => trivial
        print("Index is empty. No files to checksum.")
        with open(checksums_file, "wb") as f_out:
            # We'll write a minimal structure with 0 fileIdCount, 0 checksums
            f_out.write(struct.pack("<IIII", 0x14893721, 0, 0, 0))
        return

    # 2) Read the entire .dat
    with open(dat_file, "rb") as f_dat:
        dat_content = f_dat.read()

    # 3) Build chunk-based checksums
    #    for each file in ascending file_id order
    sorted_ids = sorted(index_data.keys())
    highest_id = max(sorted_ids)

    checksums_dict = {}  # { file_id: [list_of_4byte_crc_structs] }

    for file_id in sorted_ids:
        info = index_data[file_id]
        offset = info["offset"]
        length = info["length"]

        file_bytes = dat_content[offset : offset + length]

        chunk_list = []
        for chunk_start in range(0, length, CHUNK_SIZE):
            chunk_end = min(chunk_start + CHUNK_SIZE, length)
            chunk_data = file_bytes[chunk_start : chunk_end]
            csum_val = adler_crc32(chunk_data)
            csum_bytes = struct.pack("<I", csum_val)
            chunk_list.append(csum_bytes)

        checksums_dict[file_id] = chunk_list

    # 4) Fill in missing IDs from 0..highest_id with zero
    file_id_count = highest_id + 1
    indextable = bytearray()
    checksumtable = bytearray()
    running_offset = 0

    for fid in range(file_id_count):
        if fid not in checksums_dict:
            # missing => (0, 0)
            indextable += struct.pack("<II", 0, 0)
        else:
            chunk_list = checksums_dict[fid]
            chunk_count = len(chunk_list)
            indextable += struct.pack("<II", chunk_count, running_offset)
            for csum_b in chunk_list:
                checksumtable += csum_b
            running_offset += chunk_count

    checksum_count = running_offset

    # 5) Build the final .checksums file
    format_code = 0x14893721
    dummy0 = 0
    out_buf = bytearray()
    out_buf += struct.pack("<IIII", format_code, dummy0, file_id_count, checksum_count)
    out_buf += indextable
    out_buf += checksumtable

    with open(checksums_file, "wb") as f_out:
        f_out.write(out_buf)

    print(f"Created .checksums at: {checksums_file}")
    print(f" - file_id range: 0..{file_id_count - 1}")
    print(f" - total checksums: {checksum_count}")
    print(f" - chunk size: 32 KB (0x8000)")
    print("One checksum per 32 KB chunk per file. Done.")

def main():
    if len(sys.argv) < 3:
        print(f"Usage: python {os.path.basename(__file__)} <app_id> <app_version>")
        sys.exit(1)

    app_id_str = sys.argv[1]
    app_version_str = sys.argv[2]

    # If app_id is hex, convert
    if app_id_str.lower().startswith("0x"):
        app_id_str = str(int(app_id_str, 16))

    generate_32kb_checksums(app_id_str, app_version_str)

if __name__ == "__main__":
    main()
