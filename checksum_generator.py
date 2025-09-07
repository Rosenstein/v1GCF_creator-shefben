import struct
import zlib
import sys
import pickle
import os

def calculate_chunk_checksum(data_block: bytes) -> int:
    """
    Calculate the checksum for a given data block:
    Adler32(0, data_block) XOR CRC32(0, data_block).
    """
    adler = zlib.adler32(data_block, 0) & 0xFFFFFFFF
    return adler

def parse_manifest_for_version(manifest_file: str) -> int:
    """
    Reads the manifest to extract the app version.
    """
    with open(manifest_file, "rb") as f:
        data = f.read(12)
        _, _, manif_appversion = struct.unpack("<III", data)
    return manif_appversion

def create_checksums(
    manifest_file: str,
    index_file: str,
    dat_file: str,
    app_id: int,
    app_version_str: str,
    output_filename: str = None
):
    """
    Generates a .checksums file based on the manifest, index, and dat files.
    """
    manifest_appversion = parse_manifest_for_version(manifest_file)

    # Load the .index file
    with open(index_file, "rb") as f_idx:
        index_data = pickle.load(f_idx)

    # Process each file in the .index and calculate checksums
    all_checksums = []
    file_id_entries = []

    running_index = 0
    with open(dat_file, "rb") as f_dat:
        for file_id, info in index_data.items():
            offset = info['offset']
            length = info['length']

            # Read the file data from the .dat file
            f_dat.seek(offset)
            file_data = f_dat.read(length)

            # Calculate the checksum for the entire file
            file_checksum = calculate_chunk_checksum(file_data)

            # Save the checksum and update file_id entries
            file_id_entries.append((1, running_index))  # 1 checksum for the whole file
            all_checksums.append(file_checksum)
            running_index += 1

    # Build the .checksums file structure
    header_version = 1
    format_code = 0x14893721
    dummy0 = 1

    file_id_count = len(file_id_entries)
    checksum_count = len(all_checksums)

    out_buf = bytearray()

    # 1) ChecksumDataContainer
    out_buf += struct.pack("<II", header_version, 0)  # Placeholder for ChecksumSize

    # 2) LatestApplicationVersion
    out_buf += struct.pack("<I", manifest_appversion)

    # 3) FileIdChecksumTableHeader
    out_buf += struct.pack("<IIII", format_code, dummy0, file_id_count, checksum_count)

    # 4) FileIdChecksumTableEntry array
    for (ccount, first_index) in file_id_entries:
        out_buf += struct.pack("<II", ccount, first_index)

    # 5) ChecksumEntry array
    for ch in all_checksums:
        out_buf += struct.pack("<I", ch)

    # The following is NOT used for Beta 1 checksum files
    """# 6) 128-byte signature placeholder
    out_buf += b'\x00' * 128"""

    # Update ChecksumSize
    checksum_size = len(out_buf) - 12
    struct.pack_into("<I", out_buf, 4, checksum_size)

    # Write the .checksums file
    if output_filename is None:
        output_filename = f"{app_id}_{app_version_str}.checksums"
    with open(output_filename, "wb") as fout:
        fout.write(out_buf)

    print(f"Checksum file generated: {output_filename}")

def main():
    if len(sys.argv) < 5:
        print("Usage: python checksum_generator.py <manifest_file> <index_file> <dat_file> <app_id> <app_version_str> [<output_checksum_file>]")
        sys.exit(1)

    manifest_file = sys.argv[1]
    index_file = sys.argv[2]
    dat_file = sys.argv[3]
    app_id_str = sys.argv[4]
    app_version_str = sys.argv[5]

    if len(sys.argv) > 6:
        output_file = sys.argv[6]
    else:
        output_file = None

    try:
        app_id = int(app_id_str, 16) if app_id_str.lower().startswith('0x') else int(app_id_str)
    except ValueError:
        print("Invalid app_id. Provide as decimal or '0x'-prefixed hex.")
        sys.exit(1)

    for fpath in (manifest_file, index_file, dat_file):
        if not os.path.isfile(fpath):
            print(f"ERROR: File not found: {fpath}")
            sys.exit(1)

    create_checksums(
        manifest_file=manifest_file,
        index_file=index_file,
        dat_file=dat_file,
        app_id=app_id,
        app_version_str=app_version_str,
        output_filename=output_file
    )

if __name__ == "__main__":
    main()
