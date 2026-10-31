package com.voxscribe.android

/**
 * A port of the part of Python's difflib.SequenceMatcher the Windows app uses,
 * so term repair and Teach your voice judge text the same way on both. No junk
 * heuristic: Windows only compares short strings and word lists, where difflib
 * never applies it.
 */
class SequenceMatcher<T>(private val a: List<T>, private val b: List<T>) {

    /** A run of [size] equal items starting at a[[aStart]] and b[[bStart]]. */
    data class Block(val aStart: Int, val bStart: Int, val size: Int)

    private val positionsInB: Map<T, List<Int>> = buildMap<T, MutableList<Int>> {
        b.forEachIndexed { j, item -> getOrPut(item) { mutableListOf() }.add(j) }
    }

    /** The longest equal run in a[aLo, aHi) and b[bLo, bHi); the earliest one on a tie. */
    private fun longestMatch(aLo: Int, aHi: Int, bLo: Int, bHi: Int): Block {
        var bestI = aLo
        var bestJ = bLo
        var bestSize = 0
        var lengths = HashMap<Int, Int>()
        for (i in aLo until aHi) {
            val next = HashMap<Int, Int>()
            for (j in positionsInB[a[i]].orEmpty()) {
                if (j < bLo) continue
                if (j >= bHi) break
                val k = (lengths[j - 1] ?: 0) + 1
                next[j] = k
                if (k > bestSize) {
                    bestI = i - k + 1
                    bestJ = j - k + 1
                    bestSize = k
                }
            }
            lengths = next
        }
        return Block(bestI, bestJ, bestSize)
    }

    /** The equal runs in order, adjacent runs joined, ending with a (len a, len b, 0) marker. */
    val matchingBlocks: List<Block> by lazy {
        val queue = ArrayDeque(listOf(intArrayOf(0, a.size, 0, b.size)))
        val found = mutableListOf<Block>()
        while (queue.isNotEmpty()) {
            val (aLo, aHi, bLo, bHi) = queue.removeLast()
            val match = longestMatch(aLo, aHi, bLo, bHi)
            if (match.size == 0) continue
            found += match
            if (aLo < match.aStart && bLo < match.bStart) {
                queue.addLast(intArrayOf(aLo, match.aStart, bLo, match.bStart))
            }
            if (match.aStart + match.size < aHi && match.bStart + match.size < bHi) {
                queue.addLast(intArrayOf(match.aStart + match.size, aHi, match.bStart + match.size, bHi))
            }
        }
        found.sortWith(compareBy({ it.aStart }, { it.bStart }))
        val joined = mutableListOf<Block>()
        var current: Block? = null
        for (block in found) {
            val c = current
            current = if (c != null && c.aStart + c.size == block.aStart && c.bStart + c.size == block.bStart) {
                c.copy(size = c.size + block.size)
            } else {
                c?.let { joined += it }
                block
            }
        }
        current?.let { joined += it }
        joined += Block(a.size, b.size, 0)
        joined
    }

    /** 2 * matches / total length, from 0 to 1; 1 for two empty sequences. */
    fun ratio(): Double {
        val total = a.size + b.size
        if (total == 0) return 1.0
        return 2.0 * matchingBlocks.sumOf { it.size } / total
    }

    companion object {
        fun ratio(a: String, b: String): Double = SequenceMatcher(a.toList(), b.toList()).ratio()
    }
}
