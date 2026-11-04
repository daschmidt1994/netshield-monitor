package io.github.daschmidt1994.netshield

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import io.github.daschmidt1994.netshield.data.CredentialStore
import io.github.daschmidt1994.netshield.data.Repository
import io.github.daschmidt1994.netshield.data.db.AppDatabase
import io.github.daschmidt1994.netshield.work.MonitorWorker
import java.util.concurrent.TimeUnit

class NetShieldApp : Application() {
    lateinit var store: CredentialStore
        private set
    lateinit var repository: Repository
        private set
    lateinit var database: AppDatabase
        private set

    override fun onCreate() {
        super.onCreate()
        store = CredentialStore(this)
        database = AppDatabase.get(this)
        repository = Repository(store, database.cache())
        createChannels()
        scheduleMonitor()
    }

    fun scheduleMonitor() {
        // 15 minutes is the minimum interval for periodic work on Android.
        val req = PeriodicWorkRequestBuilder<MonitorWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork("netshield-monitor", ExistingPeriodicWorkPolicy.UPDATE, req)
    }

    private fun createChannels() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL_CRITICAL, getString(R.string.channel_critical), NotificationManager.IMPORTANCE_HIGH))
        nm.createNotificationChannel(NotificationChannel(CHANNEL_WARNING, getString(R.string.channel_warning), NotificationManager.IMPORTANCE_DEFAULT))
        nm.createNotificationChannel(NotificationChannel(CHANNEL_BACKEND, getString(R.string.channel_backend), NotificationManager.IMPORTANCE_DEFAULT))
    }

    companion object {
        const val CHANNEL_CRITICAL = "critical"
        const val CHANNEL_WARNING = "warning"
        const val CHANNEL_BACKEND = "backend"
    }
}
