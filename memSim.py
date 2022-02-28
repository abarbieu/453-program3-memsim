import argparse
import pandas as pd
from collections import OrderedDict

BLOCKSIZE = 256
TLBSIZE = 16


def checkFrames(frames):
    frames = int(frames)
    if frames > 256 or frames <= 0:
        raise argparse.ArgumentTypeError(f"Number of frames should be between 1 and 256 "
                                         "Given: {frames} is outside this range")
    return frames


def searchTLB(TLB, pageNumber):
    if pageNumber in TLB:
        frameNumber = TLB[pageNumber]
        del TLB[pageNumber]
        TLB[pageNumber] = frameNumber  # for FIFO, update use date
        return frameNumber
    return None


def addTLB(TLB, pageNumber, frameNumber, iter):
    if len(TLB) >= TLBSIZE:
        TLB.popitem(last=False)  # get rid of oldest entry
    TLB[pageNumber] = frameNumber


def findNewFrame(PT, algorithm="FIFO"):
    if algorithm == "FIFO":
        pass
    elif algorithm == "LRU":
        pass
    else:
        raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Virtal Memory mini simulator for CSC 453 W22')
    parser.add_argument(
        "referencefile", help="File containing list of logical memory addresses")
    parser.add_argument("frames", type=checkFrames, default=256,
                        help="Number of frames of the physical address space")
    parser.add_argument("pra", choices=[
                        "FIFO", "LRU", "OPT"], default="FIFO", help="Page replacement algorithm")

    args = parser.parse_args()

    # Backing store, hard disk, the memory we read from
    BS = open("./BACKING_STORE.bin")

    # Page table, 256 entires indexed by page number (0-256), contains frame number (0-frames),
    # final active bit, iteration # used, iteration # last referenced
    PT = pd.DataFrame()

    # Transition lookaside buffer, ordered to support FIFO, 16 entries of active pages
    TLB = OrderedDict()

    # Main memory, a list of frames# of frames of size 256
    RAM = [None] * args.frames
    ramPointer = 0

    # Statistics for misses etc.
    tlbMisses = 0
    tlbHits = 0
    pageFaults = 0

    with open(args.referencefile) as f:
        references = []
        for line in f.readlines():
            references.append(int(line.strip('\n')))

    iter = 0
    # main loop, simulates time passing and job queries
    # iter represents time, used for LRU etc.
    for reference in references:
        # parse reference address
        addr = format(reference, '016b')
        pageNumber = int(addr[:8], 2)  # it is in base 2
        pageOffset = int(addr[8:], 2)

        # check TLB
        frameNumber = None
        frameNumber = searchTLB(pageNumber)

        # if not in TLB, look in page table, record TLB miss
        if frameNumber is None:
            if pageNumber in PT.index:  # if PT doesnt have page number, frame number remains None
                frameNumber = PT.loc[pageNumber, "frameNumber"]
            tlbMisses += 1
        else:
            tlbHits += 1

        frameData = None

        # if not in page table, find in backing store, record page fault
        if frameNumber is None or not PT.loc[pageNumber, "active"]:
            # hard miss, find data from disk
            pageFaults += 1
            BS.seek(pageNumber * BLOCKSIZE)
            frameData = BS.read(BLOCKSIZE)

            if frameNumber is None:  # RAM hasn't been filled yet, get next available slot
                frameNumber = ramPointer
                ramPointer += 1
                if ramPointer >= 256:
                    # if this happens, the virtual address is larger than the page table
                    raise ValueError(
                        "Index error, memory address outside of range")
            else:
                # page is inactive, find new frame
                frameNumber = findNewFrame(PT, algorithm=args.pra)

            # set page initialization time to current iter
            PT.loc[pageNumber, "init"] = iter
            # page is resident in main memory!
            RAM[frameNumber] = frameData
        else:
            # if page already resident, just get the data
            frameData = RAM[frameNumber]

        # add page to page table or update, set to active, set reference time to curr iter
        PT.loc[pageNumber, ["frameNumber", "active", "ref"]] = [
            frameNumber, True, iter]

        # add page to TLB. If already in TLB, nothing happens
        addTLB(pageNumber, frameNumber, iter)

        # requested data, entry in data
        dataByte = ord(dataByte[pageOffset])
        # data is signed
        if dataByte > (BLOCKSIZE/2) + 1:
            dataByte = (BLOCKSIZE-dataByte) * -1

        print(
            f"{reference}, {dataByte}, {frameNumber}, {''.join(['%02X' % ord(x) for x in dataByte]).strip()}")

        iter += 1
