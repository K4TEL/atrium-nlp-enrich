# import sys, os
# infile, outdir, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
# with open(infile, 'r', encoding='utf-8') as f: text = f.read().strip()
# if not text: sys.exit(0)
# words = text.split()
# for i, x in enumerate(range(0, len(words), limit)):
#     with open(os.path.join(outdir, f"chunk_{i}.txt"), 'w', encoding='utf-8') as out:
#         out.write(" ".join(words[x:x+limit]))

import sys
import os


def write_chunk(output_dir, chunk_index, words_list):
    """Helper to write a list of words to a file."""
    filename = os.path.join(output_dir, f"chunk_{chunk_index}.txt")
    with open(filename, 'w', encoding='utf-8') as out:
        out.write(" ".join(words_list))


def main():
    # Basic argument validation
    if len(sys.argv) < 4:
        print("Usage: chunk.py <infile> <outdir> <word_limit>")
        sys.exit(1)

    infile = sys.argv[1]
    outdir = sys.argv[2]
    limit = int(sys.argv[3])

    # Ensure output directory exists
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    with open(infile, 'r', encoding='utf-8') as f:
        text = f.read().strip()

    if not text:
        sys.exit(0)

    words = text.split()
    current_chunk = []
    chunk_count = 0

    # Iterate through all words
    i = 0
    while i < len(words):
        current_chunk.append(words[i])
        i += 1

        # Check if the current buffer has reached the word limit
        if len(current_chunk) >= limit:
            cut_index = -1

            # Scan backwards from the end of the current chunk to find punctuation.
            # We limit the lookback (e.g., 100 words) to prevent losing too much context
            # if a sentence is extremely long.
            lookback_limit = max(0, len(current_chunk) - 100)

            for j in range(len(current_chunk) - 1, lookback_limit, -1):
                word = current_chunk[j]
                # Check if the word ends with standard sentence delimiters
                if word and word[-1] in ['.', '?', '!']:
                    cut_index = j + 1  # Cut immediately after the punctuation word
                    break

            # Fallback: If no punctuation is found (e.g., a very long list),
            # we are forced to split at the hard limit.
            if cut_index == -1:
                cut_index = len(current_chunk)

            # Write the valid sentence block to a file
            write_chunk(outdir, chunk_count, current_chunk[:cut_index])
            chunk_count += 1

            # The remaining words (if we split early) become the start of the next chunk
            leftovers = current_chunk[cut_index:]
            current_chunk = leftovers

    # Write any remaining words in the buffer (the final chunk)
    if current_chunk:
        write_chunk(outdir, chunk_count, current_chunk)


if __name__ == "__main__":
    main()