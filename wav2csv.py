"""
Connvert of data in a WAV file to a CSV file.
"""

import sys
import struct
import wave
import numpy as np
import matplotlib.pyplot as plt

import auto_record

def convert(filename: str) -> np.ndarray:
    """
    Read filename as a WAVE file, return a normalized numpy array
    """
    with wave.open(filename, 'rb') as wf:
        # Assume we have 16bit 
        channels = wf.getnchannels()
        values = []

        while len(data := wf.readframes(1000)) > 0:
            count = len(data) // 2
            fmt = "<%dh" % (count)      # 16 bit Little Endian
            shorts = struct.unpack(fmt, data)
            values.extend(shorts)

    result = np.array(values, dtype=int)
    result = np.reshape(result, (-1, channels))
    return result

def read_data_blocks(filename: str) -> list[auto_record.AudioDataBlock]:
    result = []
    with wave.open(filename, 'rb') as wf:
        while len(data := wf.readframes(1000)) > 0:
            block = auto_record.AudioDataBlock(data)
            result.append(block)
    return result

def get_volume_array(blocks: list[auto_record.AudioDataBlock]) -> np.ndarray:
    return np.array([ f.volume for f in blocks])

def write_array(filename: str, array: np.ndarray) -> None:
    """
    Use np.savetxt to write the array to a CSV file
    """
    print(f"Write file: {filename_csv}")
    np.savetxt(filename_csv, array, delimiter=",")
    print("Done")

def plot_array(array: np.ndarray) -> None:
    """
    Display a plot of an audio array.
    """
    plt.plot(array)
    plt.xlabel("sample no")
    plt.ylabel('value')
    plt.grid(True)
    plt.show()

def plot_stairs(array: np.ndarray) -> None:
    """
    Display a plot of an array as stairs
    """
    plt.stairs(array, fill=True)
    plt.xlabel("sample no")
    plt.ylabel('value')
    plt.grid(True)
    plt.show()

def normalize(array: np.ndarray) -> np.ndarray:
    """
    Return an array with values normalized between 1 and -1
    """
    return array / 32768.0


if __name__ == '__main__':
    """
    Read a wave file and write a CSV
    """
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <wav file>")
        sys.exit(-1)
    filename = sys.argv[1]
    array = convert(filename)
    filename_csv = f"{filename}.csv"
    write_array(filename_csv, array)


