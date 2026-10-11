package com.voxscribe.android

import android.content.Context

/** The Pro license key kept on this phone. Checking it never needs the network. */
object LicenseStore {
    private const val PREFS_NAME = "voxscribe_license"
    private const val KEY_LICENSE = "license_key"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun isPro(context: Context): Boolean {
        val stored = prefs(context).getString(KEY_LICENSE, null) ?: return false
        return LicenseKey.isValid(stored)
    }

    fun save(context: Context, key: String) {
        prefs(context).edit().putString(KEY_LICENSE, key.trim()).apply()
    }

    fun clear(context: Context) {
        prefs(context).edit().remove(KEY_LICENSE).apply()
    }
}
