package com.voxscribe.android

import android.app.Application

class VoxScribeApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashHandler.install(this)
    }
}
