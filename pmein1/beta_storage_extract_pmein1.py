import zlib
import pickle

def extract_and_decompress(file_count, index_file, dat_file):
    # Load the index
    with open(index_file, 'rb') as f:
        index_data = pickle.load(f)

    # Get file information from the index
    if file_count not in index_data:
        print("Error: File number not found in index.")
        return None

    file_info = index_data[file_count]
    print(file_info)
    offset, size = file_info['offset'], file_info['length']

    # Extract and decompress the file from the .dat file
    with open(dat_file, 'rb') as f:
        f.seek(offset)
        decompressed_data = f.read(size) #was compressed_data
        #decompressed_data = zlib.decompress(compressed_data)

    with open("extract/" + str(FILE_COUNT) + ".file", "wb") as f:
        f.write(decompressed_data)
        
    print(len(decompressed_data))

    return decompressed_data

if __name__ == "__main__":
    import sys, os
    appid = sys.argv[1]
    verid = sys.argv[2]
    INDEX_FILE = appid + "_" + verid + ".index"
    dat_file = appid + "_" + verid + ".dat"
    if len(sys.argv) == 4:
        FILE_COUNT = sys.argv[3]
        data = extract_and_decompress(FILE_COUNT, INDEX_FILE, dat_file)
    else:
        with open(INDEX_FILE, 'rb') as f:
            index_data = pickle.load(f)
        #print(len(index_data))
        print(index_data)
        for FILE_COUNT in index_data:
            file_info = index_data[FILE_COUNT]
            offset, size = file_info['offset'], file_info['length']
            with open(dat_file, 'rb') as f:
                f.seek(offset)
                decompressed_data = f.read(size)
            
            print(FILE_COUNT)
        data = ""
        
    if data:
        print("Successfully extracted and decompressed the file!")
    else:
        print("No data extracted.")