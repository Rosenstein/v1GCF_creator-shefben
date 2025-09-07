# Code by Cystface-man / Shefben
# With Help From YMGVE
# And Testing By Pmein1
# Created: 10/24/2023
# Modified: 10/27/2023
# version: Beta 2

import os
import struct
import zlib
import pickle
import re

##############################################################################
# Extra function to handle the actual creation of the .checksums file.
# Because apparently, you can't handle more than one file without drooling
# all over yourself. We are now forced to do CHUNK-BASED checksums,
# and also fill gaps for missing fileIDs with zeroes, so you can waste
# fewer brain cells on basic iteration.
##############################################################################
def adler_crc32(data_block: bytes) -> int:
    """
    Calcs a single checksum: adler32(0, data)
    Because your short attention span can't handle more than a tiny function.
    """
    adler = zlib.adler32(data_block) & 0xFFFFFFFF
    return adler

def write_checksums_file(
    app_id: int,
    app_version: str,
    index_data: dict,
    dat_file_data: bytes
):
    """
    Generates a .checksums file with:
      - LatestApplicationVersion
      - FileIdChecksumTableHeader (FormatCode=0x14893721, etc.)
      - FileIdChecksumTableEntry array
      - ChecksumEntry array

    We store chunk-based checksums for each file, and ensure that file IDs that
    don?t exist are 0
    """

    CHUNK_SIZE = 0x8000

    # Let's build a dictionary for fileid => list of (chunkStart, chunkChecksum)
    # because we apparently need to hold your hand through even the simplest tasks.
    checksums = {}

    # First, figure out all the chunk checksums for actual files
    for file_id in sorted(index_data.keys()):
        info = index_data[file_id]
        offset = info['offset']
        length = info['length']

        file_bytes = dat_file_data[offset : offset + length]

        # Build the chunk list for this file_id
        chunk_list = []
        chunk_start = 0

        while chunk_start < length:
            chunk_end = min(chunk_start + CHUNK_SIZE, length)
            chunk_data = file_bytes[chunk_start : chunk_end]
            chunk_crc = adler_crc32(chunk_data)
            # Store (chunkOffset, chunkChecksum) ? the offset is optional, but we'll keep it
            chunk_list.append((chunk_start, struct.pack("<I", chunk_crc)))
            chunk_start += CHUNK_SIZE

        checksums[file_id] = chunk_list

    # Now find the max ID we encountered, so we know how far to iterate
    last_id = max(checksums.keys()) if checksums else 0

    # We have to build the header, the index table, and the checksum table
    # in a separate pass. That?s because we are incompetent if we try to do it
    # in one go, right? Or is that just you?
    format_code    = 0x14893721
    dummy0         = 0

    # We'll build them in separate bytearrays
    indextable = bytearray()
    checksumtable = bytearray()

    # We'll keep track of how many checksums we have total, and a running offset
    checksumoffset = 0

    # For every fileid from 0 to last_id (inclusive),
    # if the fileid doesn?t exist, we store 0,0
    # else store the chunk count and offset, then the actual checksums
    for fileid in range(last_id + 1):
        if fileid not in checksums:
            # no such file => write 0,0
            indextable += struct.pack("<II", 0, 0)
        else:
            numchecksums = len(checksums[fileid])
            # store the number of checksums for this fileid, plus offset
            indextable += struct.pack("<II", numchecksums, checksumoffset)
            # For each chunk, add the CRC to the table
            for _, chksum_bytes in checksums[fileid]:
                checksumtable += chksum_bytes
            # bump our offset by however many we just wrote
            checksumoffset += numchecksums

    # Now the total number of fileIDs is last_id + 1
    file_id_count = last_id + 1
    checksum_count = checksumoffset  # total number of chunk checksums

    out_buf = bytearray()
    out_buf += struct.pack("<IIII", format_code, dummy0, file_id_count, checksum_count)
    # Then we embed the fileId => (numchecksums, firstchecksumoffset) table
    out_buf += indextable
    # Then we append the actual checksums
    out_buf += checksumtable

    checksums_filename = f"{app_id}_{app_version}.checksums"
    with open(checksums_filename, "wb") as f_chk:
        f_chk.write(out_buf)

    print(f"Checksum file generated: {checksums_filename}. "
          f"Chunk-based checksums for real file IDs, plus zero-checksum entries "
          f"for nonexistent ones, because your code is too sloppy to handle gaps.")

def load_special_flags(filename='special_file_flags.ini'):
    """
    Load special flags from the given file and return as a dictionary.
    """
    flags = {}
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            for line in f:
                parts = line.strip().split('=')
                if len(parts) == 2:
                    flags[parts[0]] = int(parts[1], 16)  # convert hex string to int
    return flags

def parse_minfootprint_file(filename='minfootprint.txt'):
    """
    Parse the 'minfootprint.txt' file and return a list of relative file paths.
    """
    file_paths = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            for line in f:
                file_path = line.strip()
                if file_path.endswith("*"):
                    wildcard_path = file_path[:-1]  # remove the '*'
                    for root, _, files in os.walk(wildcard_path):
                        for file in files:
                            file_paths.append(os.path.relpath(os.path.join(root, file), wildcard_path))
                else:
                    file_paths.append(file_path)
    return file_paths

def generate_gcf(directory_path, app_id, app_version, fingerprint):
    """
    Generate .manifest, .dat, and .index files.
    Then call our .checksums creation function to produce the .checksums file.
    We'll do one big mouthful at once, so try not to choke on your triple bacon burger.
    """
    special_flags   = load_special_flags()
    manifest_data   = b""
    filename_string = ""
    node_index      = 0
    file_count      = 0
    dat_file_data   = b""
    index_data      = {}
    file_index      = []
    gcfdircopytable = bytearray()
    minfootprint_count = 0

    hex_fingerprint = struct.pack('4s', fingerprint.encode('ascii'))

    # Load the list of file paths from "minfootprint.txt"
    minfootprint_file_paths = parse_minfootprint_file()

    # Build up a list of items (dirs & files)
    items = []
    for root, dirs, files in os.walk(directory_path):
        if root == directory_path:
            parent_index = 0xffffffff
        else:
            parent_index = 0 if os.path.dirname(root) == directory_path \
                             else [item['index'] for item in items
                                   if item['path'] == os.path.relpath(os.path.dirname(root), directory_path)][0]

        relative_root = os.path.relpath(root, directory_path)

        items.append({
            'type': 'dir',
            'path': relative_root,
            'parent': parent_index,
            'index': node_index,
        })
        node_index += 1

        for file in files:
            relative_path = os.path.relpath(os.path.join(root, file), directory_path)
            items.append({
                'type': 'file',
                'path': relative_path,
                'parent': [item['index'] for item in items
                           if item['path'] == os.path.relpath(root, directory_path)][0],
                'index': node_index,
            })
            node_index += 1

    # Process items, create the .manifest, build .dat content, fill .index info
    for item in items:
        parent_index = item['parent']
        siblings = [i for i in items if i['parent'] == parent_index]
        current_index = item['index']

        next_index = 0
        for idx, sibling in enumerate(siblings):
            if sibling['index'] == current_index and idx < len(siblings) - 1:
                next_index = siblings[idx + 1]['index']
                break

        if item['type'] == 'dir':
            current_dir_index = item['index']

            # Child count
            child_count = sum(1 for i in items if i['parent'] == current_dir_index)
            # Child index
            children = [i for i in items if i['parent'] == current_dir_index]
            child_index = children[0]['index'] if children else 0

            # Add directory to manifest
            manifest_data += struct.pack("<IIIIIII",
                                         len(filename_string),
                                         child_count,
                                         0xffffffff,
                                         0x00000000,
                                         parent_index,
                                         next_index,
                                         child_index)

            # Add directory to filename string
            if item['path'] != ".":
                directory_name = item['path'].split(os.sep)[-1]
                filename_string += directory_name + "\x00"
            else:
                filename_string = "\x00"

            print(f"Processed directory: {item['path']}, "
                  f"Index: {current_dir_index}, Parent: {parent_index}, "
                  f"Next: {next_index}, Child: {child_index}")

        elif item['type'] == 'file':
            file_count += 1
            file_index.append(item['index'])

            # Decide if this file should be in the minfootprint or not
            wildcard_match = any(
                item['path'].startswith(path.rstrip('*'))
                for path in minfootprint_file_paths
                if path.endswith('*')
            )

            if item['path'] in minfootprint_file_paths or wildcard_match:
                flag = 0x0000400a
                minfootprint_count += 1
                gcfdircopytable += struct.pack("<I", item['index'])
                print(f"file {item['path']} added to minfootprint table!")
            elif hex(special_flags.get(item['path'], 0x00004000)) == "0x400b":
                # Another special flag condition
                flag = 0x0000400b
                minfootprint_count += 1
                gcfdircopytable += struct.pack("<I", item['index'])
                print(f"file {item['path']} added to minfootprint (no overwrite) table!")
            else:
                flag = special_flags.get(item['path'], 0x00004000)

            # Read the file data into .dat
            with open(os.path.join(directory_path, item['path']), 'rb') as f:
                content = f.read()
                offset_before = len(dat_file_data)
                dat_file_data += content
                offset_after = len(dat_file_data)

                index_data[file_count] = {
                    'offset': offset_before,
                    'length': (offset_after - offset_before)
                }

            # Add file to manifest
            manifest_data += struct.pack("<IIIIIII",
                                         len(filename_string),
                                         len(content),
                                         file_count,
                                         flag,
                                         parent_index,
                                         next_index,
                                         0)

            # Add file to filename string
            filename_string += item['path'].split(os.sep)[-1] + "\x00"

            print(f"Processed file: {item['path']}, Index: {item['index']}, "
                  f"Parent: {parent_index}, File#: {file_count}, NextFile: {next_index}, "
                  f"Flags: {hex(flag)}")

    # Prepare the final manifest
    filename_string = filename_string.encode("utf-8")
    while len(filename_string) % 4 != 0:
        filename_string += b"\x00"

    # generate header of manifest file
    manif_version           = 3  # Manifest Version
    manif_appid            = app_id
    manif_appversion       = int(app_version)
    manif_num_nodes        = item['index'] + 1
    manif_file_count       = len(file_index)
    manif_dirnamesize      = len(filename_string)
    manif_info1count       = 1
    manif_copycount        = minfootprint_count
    manif_localcount       = 0
    manif_compressedblocksize = 0x8000
    manif_totalsize        = (
        0x38
        + manif_num_nodes * 0x1c
        + manif_dirnamesize
        + (manif_info1count + manif_num_nodes) * 4
        + manif_copycount * 4
        + manif_localcount * 4
    )

    manif = struct.pack("<IIIIIIIIIIIIII",
                        manif_version,
                        manif_appid,
                        manif_appversion,
                        manif_num_nodes,
                        manif_file_count,
                        manif_compressedblocksize,
                        manif_totalsize,
                        manif_dirnamesize,
                        manif_info1count,
                        manif_copycount,
                        manif_localcount,
                        2,
                        0,
                        0)

    # Patch in the real length for filename_string
    manif = manif[:0x1c] + struct.pack("<I", len(filename_string)) + manif[0x20:]

    hashtable = struct.pack("<I", 1)
    for idx in range(manif_num_nodes - 1):
        hashtable += struct.pack("<I", idx)
    hashtable += struct.pack("<I", (manif_num_nodes - 1) | 0x80000000)

    final_manifest = manif + manifest_data + filename_string + hashtable + gcfdircopytable

    # Write the fingerprint + adler32 into bytes [0x30..0x38]
    final_manifest = final_manifest[:0x30] + b"\x00" * 8 + final_manifest[0x38:]
    checksum_value = hex_fingerprint + struct.pack("<I", zlib.adler32(final_manifest, 0) & 0xFFFFFFFF)
    final_manifest = final_manifest[:0x30] + checksum_value + final_manifest[0x38:]

    # Write out the final .manifest
    manifest_fname = f"{app_id}_{app_version}.manifest"
    with open(manifest_fname, "wb") as f_out:
        f_out.write(final_manifest)

    # Write the .dat file
    dat_fname = f"{app_id}_{app_version}.dat"
    with open(dat_fname, "wb") as f_out:
        f_out.write(dat_file_data)

    # Write the .index file
    index_fname = f"{app_id}_{app_version}.index"
    with open(index_fname, "wb") as f_out:
        pickle.dump(index_data, f_out, protocol=2)

    print(f"Generated: {manifest_fname}, {dat_fname}, {index_fname}")

    ############################################################################
    # Finally, create the .checksums file using the improved chunk-based logic,
    # while also ensuring zero entries for missing IDs. This is probably more
    # than that puny hamster-wheel of a brain can handle.
    ############################################################################
    write_checksums_file(
        app_id=app_id,
        app_version=app_version,
        index_data=index_data,
        dat_file_data=dat_file_data
    )

def main():
    import sys

    if (len(sys.argv) < 2 or (len(sys.argv) < 5 and sys.argv[1].lower() != "help")):
        print("Usage: python manifest_generator.py <directory_path> <app_id> <app version> <unique 4 character fingerprint>")
        print("Or for help use: python manifest_generator.py help")
        sys.exit(1)

    if (sys.argv[1].lower() == "help" ):
        print("This tool is used to take raw files and generate a manifest that can be sent to beta 1 and beta 2 steam clients.")
        print("It also takes each file, compresses it and adds it to a storage (.dat file) for later retrieval on the server when the client requests a certain file id.")
        print("and generates a '.index' file which holds where in the '.dat' file a specific fileid is and how big that file is in there.")
        print("App_id Must be a number with NO letters or special characters.")
        print("App version must also be a number, do not use letters, periods or special characters.")
        print("The unique 4 character finger print is used for identification by steam to determine which cache it is looking for.")
        print("The 4 characters can be anything (letters, numbers, special characters) but must be exactly 4 characters.")
        print("")
        print("------------------------------------------------------------------------------------------------------------")
        print("")
        print("Usage: python manifest_generator.py <directory_path> <app_id> <app version> <unique 4 character fingerprint>")
        print("Or for help use: python manifest_generator.py help")
        sys.exit(1)

    directory_path = sys.argv[1]

    # You pass the app_id in hex, so we parse it:
    app_id = int(sys.argv[2], 16)
    # We forcibly remove non-digit characters from app_version:
    app_version = "".join(re.findall(r'\d', sys.argv[3]))

    fingerprint = sys.argv[4]

    generate_gcf(directory_path, app_id, app_version, fingerprint)

if __name__ == "__main__":
    main()
