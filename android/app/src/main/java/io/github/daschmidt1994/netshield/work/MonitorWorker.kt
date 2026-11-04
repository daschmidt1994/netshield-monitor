package io.github.daschmidt1994.netshield.work

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import io.github.daschmidt1994.netshield.MainActivity
import io.github.daschmidt1994.netshield.NetShieldApp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.ApiFailure
import io.github.daschmidt1994.netshield.data.db.StoredNotification
import kotlinx.coroutines.flow.first

/**
 * Periodic background check (every ~15 min, Android minimum):
 *  - fetches new backend notifications (alerts, spikes, outages) and shows them locally,
 *  - notifies when the backend itself is unreachable (rate-limited to once per 6 h).
 * Real-time push is provided by ntfy on the backend side; this worker is the fallback/offline detector.
 */
class MonitorWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val app = applicationContext as NetShieldApp
        val store = app.store
        store.current() ?: return Result.success()
        val prefs = store.prefs.first()
        try {
            val last = store.lastNotificationId()
            val items = app.repository.fresh { notifications(afterId = last ?: 0, limit = 50) }.items
            app.database.cache().putNotifications(items.map {
                StoredNotification(it.id, it.ts, it.kind, it.severity, it.title, it.message, it.host)
            })
            if (last != null && prefs.notifyEnabled) {
                items.filter { !prefs.notifyCriticalOnly || it.severity == "critical" }.take(5).forEach {
                    notify(it.id.toInt(), it.title, it.message,
                        if (it.severity == "critical") NetShieldApp.CHANNEL_CRITICAL else NetShieldApp.CHANNEL_WARNING)
                }
            }
            val newest = items.maxOfOrNull { it.id } ?: last ?: 0
            if (last == null) {
                // first run: remember the newest id without replaying history
                val latest = app.repository.fresh { notifications(limit = 1) }.items.firstOrNull()?.id ?: 0
                store.setLastNotificationId(latest)
            } else {
                store.setLastNotificationId(newest)
            }
            app.database.cache().pruneNotifications(System.currentTimeMillis() / 1000 - 30 * 86400)
            return Result.success()
        } catch (e: ApiFailure.Unauthorized) {
            return Result.success()
        } catch (e: Exception) {
            val now = System.currentTimeMillis()
            if (prefs.notifyEnabled && prefs.notifyBackendOffline && now - store.lastOfflineNotice() > 6 * 3600_000L) {
                notify(1, applicationContext.getString(R.string.backend_offline_title),
                    applicationContext.getString(R.string.backend_offline_text), NetShieldApp.CHANNEL_BACKEND)
                store.setLastOfflineNotice(now)
            }
            return Result.success()
        }
    }

    private fun notify(id: Int, title: String, text: String, channel: String) {
        val ctx = applicationContext
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
            android.os.Build.VERSION.SDK_INT >= 33) return
        val pi = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val n = NotificationCompat.Builder(ctx, channel)
            .setSmallIcon(R.drawable.ic_shield)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify(id, n)
    }
}
