import pickle
import sys

if len(sys.argv) != 2:
    print("Usage: python inspect_index.py <index_file>")
    sys.exit(1)

index_file = sys.argv[1]

with open(index_file, "rb") as f:
    index_data = pickle.load(f)
    print("Index Data Structure:")
    for key, value in index_data.items():
        print(f"Key: {key}, Value: {value}")
