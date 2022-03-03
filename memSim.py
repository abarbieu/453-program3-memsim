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


def addTLB(TLB, pageNumber, frameNumber):
    if len(TLB) > TLBSIZE:
        TLB.popitem(last=False)  # get rid of oldest entry
    TLB[pageNumber] = frameNumber


def evictTLB(TLB, pageNumber):
    del TLB[pageNumber]


def findNewFrame(PT, algorithm, pagerefs):
    # Find the page chosen to be evicted, returns open frame number and chosen page
    frameNumber = None
    evictedPage = None
    activePages = PT[PT["active"]]
    evictedIndex = None

    if algorithm == "FIFO":
        evictedIndex = activePages["init"].argmin()
    elif algorithm == "LRU":
        evictedIndex = activePages["ref"].argmin()
    elif algorithm == "OPT":
        unreferenced = [
            ref for ref in activePages.index if ref not in pagerefs]
        if len(unreferenced) > 0:
            # if a page will never be referenced again, evict it first
            evictedPage = unreferenced[0]
        else:
            nextrefs = [ref for ref in pagerefs if ref in activePages.index]
            evictedPage = nextrefs[-1]  # return latest referenced page
    else:
        raise NotImplementedError
    if evictedPage is None:
        # evicted ID was index into active pages, need index into PT
        evictedPage = activePages.index[evictedIndex]
    PT.loc[evictedPage, "active"] = False
    frameNumber = PT.loc[evictedPage]["frameNumber"]

    return (int(frameNumber), evictedPage)


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
    BS = open("./BACKING_STORE.bin", 'rb')

    # Page table, 256 entires indexed by page number (0-256), contains frame number (0-frames),
    # final active bit, iteration # used, iteration # last referenced
    PT = pd.DataFrame()

    # Transition lookaside buffer, ordered to support FIFO, 16 entries of active pages
    TLB = OrderedDict()

    # Main memory, a list of frames # of frames
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
    refPageNs = list(pd.Series(references).apply(
        lambda x: format(x, '016b')).apply(lambda x: int(x[:8], 2)))  # for OPT algorithm

    # main loop, simulates time passing and job queries
    # iter represents time, used for LRU etc.
    for reference in references:
        # parse reference address
        addr = format(reference, '016b')
        pageNumber = int(addr[:8], 2)  # it is in base 2
        pageOffset = int(addr[8:], 2)

        # check TLB
        frameNumber = None
        frameNumber = searchTLB(TLB, pageNumber)

        # if not in TLB, look in page table, record TLB miss
        if frameNumber is None:
            if pageNumber in PT.index:  # if PT doesnt have page number, frame number remains None
                frameNumber = int(PT.loc[pageNumber, "frameNumber"])
            tlbMisses += 1
        else:
            tlbHits += 1

        frameData = None

        # if not in page table, find in backing store, record page fault
        if frameNumber is None or not PT.loc[pageNumber, "active"]:
            # hard miss, fetch data from disk
            pageFaults += 1
            BS.seek(pageNumber * BLOCKSIZE)
            frameData = BS.read(BLOCKSIZE)

            # page is unititialized or inactive, find new frame
            if ramPointer < args.frames:
                # RAM hasn't been filled yet, get next available slot
                frameNumber = ramPointer
                ramPointer += 1
            else:
                # Evict a page :(
                frameNumber, evictedPage = findNewFrame(
                    PT, args.pra, refPageNs[iter:])
                evictTLB(TLB, evictedPage)

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
        addTLB(TLB, pageNumber, frameNumber)

        # requested data, entry in data
        referencedByte = frameData[pageOffset]
        # data is signed
        if referencedByte > (BLOCKSIZE/2) + 1:
            referencedByte = (BLOCKSIZE-referencedByte) * -1

        print(
            f"{reference}, {referencedByte}, {frameNumber}, {''.join(['%02X' % x for x in frameData]).strip()}")

        iter += 1
    print(
        f"Page Table:\n\tFaults: {pageFaults}\n\tFault Rate: {100*(pageFaults/len(references))}%")
    print(
        f"TLB:\n\tHits: {tlbHits}\n\tMisses: {tlbMisses}\n\tHit Rate: {100*(tlbHits/len(references))}%")
