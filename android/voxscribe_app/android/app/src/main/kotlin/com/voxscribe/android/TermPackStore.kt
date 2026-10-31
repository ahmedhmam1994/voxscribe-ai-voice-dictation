package com.voxscribe.android

import android.content.Context
import java.io.File

/**
 * Where the term packs live: the built-in ones in assets/packs, the user's
 * imported ones in the app's own files (never backed up, see the manifest).
 * Which packs are switched on is saved with the text tools.
 */
object TermPackStore {
    private const val ASSET_DIR = "packs"
    private const val USER_DIR = "packs"
    private val safeName = Regex("[^\\w \\-]")

    /** What the settings screen lists for one pack. */
    data class Info(val id: String, val label: String, val count: Int, val user: Boolean)

    private val builtinCache = HashMap<String, TermPacks.Pack>()
    private val userCache = HashMap<String, Pair<Long, TermPacks.Pack>>()

    private fun userDir(context: Context) = File(context.filesDir, USER_DIR)

    /** The user pack file for [id], or null for a built-in pack or a name that tries to leave the folder. */
    private fun userFile(context: Context, id: String): File? {
        if (!id.startsWith(TermPacks.USER_PREFIX)) return null
        val name = id.removePrefix(TermPacks.USER_PREFIX)
        if (name.isEmpty() || safeName.containsMatchIn(name)) return null
        return File(userDir(context), "$name.txt")
    }

    @Synchronized
    fun pack(context: Context, id: String): TermPacks.Pack {
        val empty = TermPacks.Pack(emptyList(), emptyList())
        if (TermPacks.BUILTIN.any { it.first == id }) {
            return builtinCache.getOrPut(id) {
                runCatching {
                    context.assets.open("$ASSET_DIR/$id.txt").bufferedReader().use { TermPacks.parse(it.readText()) }
                }.getOrDefault(empty)
            }
        }
        val file = userFile(context, id)?.takeIf { it.isFile } ?: return empty
        val modified = file.lastModified()
        userCache[id]?.let { (at, pack) -> if (at == modified) return pack }
        val pack = runCatching { TermPacks.parse(file.readText()) }.getOrDefault(empty)
        userCache[id] = modified to pack
        return pack
    }

    /** The built-in packs, then the user's own by name. Packs with no terms are left out. */
    fun available(context: Context): List<Info> {
        val builtin = TermPacks.BUILTIN.map { (id, label) -> Info(id, label, pack(context, id).terms.size, false) }
        val user = userDir(context).listFiles { f -> f.isFile && f.name.endsWith(".txt") }.orEmpty()
            .sortedBy { it.name }
            .map { file ->
                val id = TermPacks.USER_PREFIX + file.nameWithoutExtension
                Info(id, file.nameWithoutExtension, pack(context, id).terms.size, true)
            }
        return (builtin + user).filter { it.count > 0 }
    }

    /** Saves [text] as a user pack named after [fileName]. Throws IllegalArgumentException with what to tell the user. */
    fun import(context: Context, fileName: String, text: String): Info {
        require(text.toByteArray().size <= TermPacks.MAX_FILE_BYTES) {
            "That file is too big for a term pack (1 MB at most)."
        }
        val terms = TermPacks.parse(text).terms
        require(terms.isNotEmpty()) { "No terms found. A pack is a text file with one term per line." }
        val name = safeName.replace(fileName.substringBeforeLast('.'), "").trim().take(40).ifEmpty { "My pack" }
        val dir = userDir(context)
        dir.mkdirs()
        File(dir, "$name.txt").writeText(text)
        return Info(TermPacks.USER_PREFIX + name, name, terms.size, true)
    }

    @Synchronized
    fun remove(context: Context, id: String): Boolean {
        val file = userFile(context, id) ?: return false
        userCache.remove(id)
        return file.delete()
    }

    /** The ids switched on, stored comma separated with the text tools. None by default. */
    fun enabled(saved: TextToolsStore.Snapshot): List<String> =
        saved.termPacks.split(',').map { it.trim() }.filter { it.isNotEmpty() }

    fun packs(context: Context, ids: List<String>): List<TermPacks.Pack> = ids.map { pack(context, it) }
}
