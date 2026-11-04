package io.github.daschmidt1994.netshield.ui.components

import java.text.DateFormat
import java.text.NumberFormat
import java.util.Date
import java.util.Locale

fun fmt(n: Long): String = NumberFormat.getIntegerInstance(Locale.getDefault()).format(n)
fun fmt(n: Double): String = NumberFormat.getNumberInstance(Locale.getDefault()).apply { maximumFractionDigits = 1 }.format(n)
fun fmtTime(ts: Long): String = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(ts * 1000))
fun fmtDuration(s: Long?): String {
    if (s == null) return "–"
    val d = s / 86400; val h = (s % 86400) / 3600; val m = (s % 3600) / 60
    return when { d > 0 -> "${d}d ${h}h"; h > 0 -> "${h}h ${m}m"; else -> "${m}m" }
}
fun countryName(code: String?): String = if (code.isNullOrBlank()) "–" else Locale("", code).getDisplayCountry(Locale.getDefault()).ifBlank { code }
fun flag(code: String?): String {
    if (code == null || code.length != 2) return "🏳️"
    val first = Character.codePointAt(code.uppercase(), 0) - 0x41 + 0x1F1E6
    val second = Character.codePointAt(code.uppercase(), 1) - 0x41 + 0x1F1E6
    return String(Character.toChars(first)) + String(Character.toChars(second))
}
