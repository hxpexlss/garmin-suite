package app.garminuebersicht.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.garminuebersicht.data.Activity
import app.garminuebersicht.data.Coach
import app.garminuebersicht.data.Night
import kotlinx.coroutines.launch
import java.time.LocalDate

private val ListPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp)

// ---------------------------------------------------------------- Heute

@Composable
fun TodayScreen(state: UiState) {
    val coach = state.coach
    LazyColumn(contentPadding = ListPadding, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { StatusLine(state) }
        if (coach == null) {
            item { if (!state.loading) Empty() }
            return@LazyColumn
        }
        item { ReadinessCard(coach) }
        item { SuggestionCard(coach) }
        item { WeekCard(coach) }
        if (coach.hints.isNotEmpty()) item {
            SectionCard("Hinweise") { coach.hints.forEach { Bullet(it) } }
        }
        item { ZonesCard(coach) }
        item {
            Text(coach.disclaimer, style = MaterialTheme.typography.labelSmall, color = LocalChartColors.current.muted,
                modifier = Modifier.padding(horizontal = 4.dp))
        }
    }
}

@Composable
fun StatusLine(state: UiState) {
    val st = state.status ?: return
    val c = LocalChartColors.current
    Column(Modifier.padding(horizontal = 4.dp)) {
        val text = when {
            st.syncing || state.syncRequested -> "Abgleich mit Garmin läuft …"
            st.lastSync != null -> "Stand: ${dateTimeLabel(st.lastSync.at)} · nächster Abgleich ${dateTimeLabel(st.nextSync)}"
            else -> "Noch kein Abgleich"
        }
        Text(text, style = MaterialTheme.typography.bodySmall, color = c.muted)
        if (st.demo) Text("Server läuft im Demo-Modus mit Beispieldaten", style = MaterialTheme.typography.bodySmall, color = c.muted)
        st.lastError?.let {
            Text("Letzter Fehler (${dateTimeLabel(it.at)}): ${it.message}", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun ReadinessCard(c: Coach) {
    val cc = LocalChartColors.current
    val color = when {
        c.readiness >= 75 -> cc.good
        c.readiness >= 55 -> cc.warn
        else -> cc.bad
    }
    SectionCard("Bereitschaft", "Aus Schlaf, HRV und Trainingsbelastung") {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("${c.readiness}", fontSize = 44.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.width(10.dp))
            Column {
                Text(c.readinessLabel.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.titleMedium)
                Text("von 100", style = MaterialTheme.typography.bodySmall, color = cc.muted)
            }
        }
        Spacer(Modifier.height(8.dp))
        Meter(c.readiness / 100f, color)
        Spacer(Modifier.height(12.dp))
        listOf(
            Triple("Schlaf", c.partSleep, c.sleepS?.let { hm(it) + (c.sleepScore?.let { s -> " · Score ${num(s)}" } ?: "") }),
            Triple("HRV", c.partHrv, c.hrvLastNight?.let { "${num(it)} ms (Schnitt ${num(c.hrvBaseline)})" }),
            Triple("Belastung", c.partLoad, c.acwr?.let { "Verhältnis 7 zu 28 Tage: ${num(it, 2)}" }),
        ).forEach { (label, value, note) ->
            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.width(76.dp))
                Meter(value / 100f, cc.s1, Modifier.weight(1f))
                Text("$value", style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.End, modifier = Modifier.width(34.dp))
            }
            if (note != null) Text(note, style = MaterialTheme.typography.labelSmall, color = cc.muted,
                modifier = Modifier.padding(start = 76.dp, bottom = 2.dp))
        }
    }
}

@Composable
private fun SuggestionCard(c: Coach) {
    val kindLabel = mapOf("rest" to "Erholung", "easy" to "Locker", "moderate" to "Moderat", "hard" to "Intensiv", "long" to "Lang")
    var showWhy by rememberSaveable { mutableStateOf(false) }
    SectionCard("Vorschlag für heute", "${kindLabel[c.kind] ?: c.kind} · ${if (c.kind == "rest") "" else c.sportLabel}".trimEnd(' ', '·')) {
        Text(c.title, fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
        if (c.durationMin.isNotEmpty() && !(c.kind == "rest" && c.durationMin.last() == 0)) {
            Text(minutesRange(c.durationMin), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(8.dp))
        c.details.forEach { Bullet(it) }
        if (c.reasons.isNotEmpty()) {
            TextButton(onClick = { showWhy = !showWhy }, contentPadding = PaddingValues(0.dp)) {
                Text(if (showWhy) "Begründung ausblenden" else "Warum dieser Vorschlag?")
            }
            if (showWhy) c.reasons.forEach { Bullet(it, MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

@Composable
private fun WeekCard(c: Coach) {
    SectionCard("Diese Woche", "Trainingszeit im Vergleich zu deinem Schnitt der letzten 4 Wochen") {
        Row(verticalAlignment = Alignment.Bottom) {
            Text(minutesHm(c.weekDoneMin), fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
            if (c.weekTargetMin > 0) Text("  von etwa ${minutesHm(c.weekTargetMin)}", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 3.dp))
        }
        if (c.weekTargetMin > 0) {
            Spacer(Modifier.height(8.dp))
            Meter(c.weekDoneMin.toFloat() / c.weekTargetMin, LocalChartColors.current.s1)
        }
    }
}

@Composable
private fun ZonesCard(c: Coach) {
    SectionCard("Pulszonen", "HFmax ${c.maxHr ?: DASH} (${c.maxHrSource ?: ""}) · Ruhepuls ${c.restingHr ?: DASH}") {
        c.zones.forEach { z ->
            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                Text(z.zone, fontWeight = FontWeight.SemiBold, modifier = Modifier.width(36.dp))
                Text(z.label, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("${z.from}–${z.to} bpm")
            }
        }
    }
}

// ---------------------------------------------------------------- Training

@Composable
fun TrainingScreen(state: UiState, onDays: (Int) -> Unit) {
    val o = state.overview
    val cc = LocalChartColors.current
    LazyColumn(contentPadding = ListPadding, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { PeriodChips(state.days, onDays) }
        if (o != null) {
            item {
                Tiles(listOf(
                    TileData("Trainings", num(o.count.toDouble()), note = "${num(o.perWeekCount, 1)} pro Woche"),
                    TileData("Trainingszeit", hm(o.durationS).removeSuffix(" h"), "h", "${hm(o.perWeekDurationS)} pro Woche"),
                    TileData("Distanz", num(o.distanceM / 1000), "km", "${num(o.perWeekDistanceM / 1000, 1)} km pro Woche"),
                    TileData("Ø Herzfrequenz", num(o.avgHr), "bpm"),
                ))
            }
            item {
                SectionCard("Trainingszeit pro Woche", "Stunden, Wochen ab Montag") {
                    ColumnChart(
                        labels = o.weekly.map { dayLabel(it.weekStart, "dd.MM.") },
                        series = listOf(Series("Stunden", cc.s1, o.weekly.map { it.hours.toFloat() })),
                        yFmt = { num(it.toDouble()) },
                        detail = { i -> o.weekly[i].let { "Woche ab ${dayLabel(it.weekStart, "dd.MM.")}: ${hm(it.hours * 3600)}, ${it.count} Trainings, ${num(it.km, 1)} km" } },
                    )
                }
            }
            item {
                SectionCard("Nach Sportart", "Trainingszeit im Zeitraum") {
                    HBars(o.sports.take(7).map { Triple(it.label, it.hours.toFloat(), hm(it.hours * 3600)) })
                }
            }
        }
        item { Text("Trainings", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 4.dp)) }
        if (state.activities.isEmpty()) item { Empty() }
        items(state.activities, key = { it.id }) { ActivityRow(it) }
    }
}

@Composable
private fun ActivityRow(a: Activity) {
    SectionCard {
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text(a.name, style = MaterialTheme.typography.titleSmall, maxLines = 1)
                Text("${dayLabel(a.date)}${a.time?.let { " · $it" } ?: ""} · ${a.typeLabel}",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(hm(a.durationS), style = MaterialTheme.typography.titleSmall)
        }
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            if ((a.distanceM ?: 0.0) > 0) Metric(km(a.distanceM))
            if ((a.distanceM ?: 0.0) > 0) Metric(pace(a.type, a.avgSpeedMs, a.distanceM))
            a.avgHr?.let { Metric("Ø ${num(it)} bpm") }
            a.trainingEffect?.let { Metric("TE ${num(it, 1)}") }
            a.calories?.let { Metric("${num(it)} kcal") }
        }
    }
}

@Composable
private fun Metric(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
}

// ---------------------------------------------------------------- Schlaf

@Composable
fun SleepScreen(state: UiState, onDays: (Int) -> Unit) {
    val o = state.overview
    val cc = LocalChartColors.current
    // Lückenlose Tagesachse über den gewählten Zeitraum
    val end = LocalDate.now()
    val dates = (state.days - 1 downTo 0).map { end.minusDays(it.toLong()).toString() }
    val byDate = state.nights.associateBy { it.date }
    val nights = dates.map { byDate[it] }
    val labels = dates.map { dayLabel(it, "dd.MM.") }
    fun h(v: Double?) = v?.let { (it / 3600).toFloat() }
    val hasStages = state.nights.any { it.deepS != null }

    LazyColumn(contentPadding = ListPadding, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { PeriodChips(state.days, onDays) }
        if (o != null) item {
            Tiles(listOf(
                TileData("Ø Schlafdauer", hm(o.avgSleepS).removeSuffix(" h"), if (o.avgSleepS != null) "h" else "", "${o.nights} Nächte"),
                TileData("Ø Sleep Score", num(o.avgScore)),
                TileData("Ø HRV", num(o.avgHrv), "ms", "über Nacht"),
                TileData("Ø Ruhepuls", num(o.avgRestingHr), "bpm"),
            ))
        }
        item {
            val stages = listOf(
                Series("Tief", cc.s1, nights.map { h(it?.deepS) }),
                Series("Leicht", cc.s2, nights.map { h(it?.lightS) }),
                Series("REM", cc.s3, nights.map { h(it?.remS) }),
                Series("Wach", cc.s4, nights.map { h(it?.awakeS) }),
            )
            SectionCard("Schlafdauer und Phasen", "Stunden pro Nacht") {
                if (hasStages) { Legend(stages.map { it.name to it.color }); Spacer(Modifier.height(6.dp)) }
                ColumnChart(
                    labels = labels,
                    series = if (hasStages) stages else listOf(Series("Schlaf", cc.s1, nights.map { h(it?.totalS) })),
                    yFmt = { num(it.toDouble()) },
                    detail = { i -> nightDetail(dates[i], nights[i]) },
                    height = 210,
                )
            }
        }
        item {
            SectionCard("Sleep Score", "0–100 pro Nacht") {
                LineChart(labels, listOf(Series("Score", cc.s1, nights.map { it?.score?.toFloat() })),
                    yFmt = { num(it.toDouble()) }, fixedMin = 0f, fixedMax = 100f, area = true,
                    detail = { i -> "${dayLabel(dates[i])}: Score ${num(nights[i]?.score)}" })
            }
        }
        item {
            val hrv = listOf(
                Series("Nacht", cc.s1, nights.map { it?.hrv?.toFloat() }),
                Series("7-Tage-Schnitt", cc.s2, nights.map { it?.hrvWeekly?.toFloat() }),
            ).filter { s -> s.values.any { it != null } }
            SectionCard("HRV über Nacht", "Millisekunden") {
                if (hrv.size > 1) { Legend(hrv.map { it.name to it.color }, line = true); Spacer(Modifier.height(6.dp)) }
                LineChart(labels, hrv, yFmt = { num(it.toDouble()) },
                    detail = { i -> "${dayLabel(dates[i])}: HRV ${num(nights[i]?.hrv)} ms, Schnitt ${num(nights[i]?.hrvWeekly)} ms" })
            }
        }
        item { Text("Nächte", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 4.dp)) }
        val list = state.nights.filter { it.totalS != null }.reversed()
        if (list.isEmpty()) item { Empty() }
        items(list, key = { it.date }) { NightRow(it) }
    }
}

private fun nightDetail(date: String, n: Night?): String {
    if (n?.totalS == null) return "${dayLabel(date)}: keine Daten"
    val parts = listOfNotNull(
        n.deepS?.let { "Tief ${hm(it)}" }, n.lightS?.let { "Leicht ${hm(it)}" },
        n.remS?.let { "REM ${hm(it)}" }, n.awakeS?.let { "Wach ${hm(it)}" },
    )
    return "${dayLabel(date)}: ${hm(n.totalS)}" + if (parts.isNotEmpty()) " (${parts.joinToString(", ")})" else ""
}

@Composable
private fun NightRow(n: Night) {
    SectionCard {
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("Nacht auf ${dayLabel(n.date)}", style = MaterialTheme.typography.titleSmall)
                Text(listOfNotNull(n.start?.let { "$it–${n.end ?: "?"}" }, n.restingHr?.let { "Ruhepuls ${num(it)}" },
                    n.hrv?.let { "HRV ${num(it)} ms" }).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(hm(n.totalS), style = MaterialTheme.typography.titleSmall)
                n.score?.let { Text("Score ${num(it)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
}

// ---------------------------------------------------------------- Einstellungen

@Composable
fun SettingsScreen(vm: AppViewModel, onSaved: () -> Unit) {
    var url by rememberSaveable { mutableStateOf(vm.settings.serverUrl) }
    var token by rememberSaveable { mutableStateOf(vm.settings.token) }
    var result by remember { mutableStateOf<String?>(null) }
    var ok by remember { mutableStateOf(false) }
    var testing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LazyColumn(contentPadding = ListPadding, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            SectionCard("Server", "Erreichbar nur über Tailscale") {
                OutlinedTextField(
                    value = url, onValueChange = { url = it; result = null },
                    label = { Text("Server-Adresse") },
                    placeholder = { Text("https://server.tailnet.ts.net") },
                    singleLine = true, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = token, onValueChange = { token = it; result = null },
                    label = { Text("App-Token") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(enabled = url.isNotBlank() && !testing, onClick = {
                        testing = true
                        scope.launch {
                            val r = vm.testConnection(url, token)
                            ok = r.isSuccess
                            result = r.fold(
                                { "Verbunden – Server ${it.version}, ${it.activityCount} Trainings, ${it.nightCount} Nächte" },
                                { it.message ?: it.toString() })
                            testing = false
                        }
                    }) { Text(if (testing) "Prüfe …" else "Verbindung testen") }
                    Button(enabled = url.isNotBlank(), onClick = { vm.saveSettings(url, token); onSaved() }) { Text("Speichern") }
                }
                result?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, style = MaterialTheme.typography.bodySmall,
                        color = if (ok) LocalChartColors.current.good else MaterialTheme.colorScheme.error)
                }
            }
        }
        item {
            SectionCard("So richtest du die Verbindung ein") {
                Bullet("Tailscale-App auf dem Handy installieren und mit demselben Tailnet wie der Server verbinden.")
                Bullet("Empfohlen: auf dem Server „tailscale serve --bg 8765“ ausführen. Adresse ist dann https://<servername>.<tailnet>.ts.net")
                Bullet("Alternativ direkt über die Tailscale-IP: http://100.x.y.z:8765 (Server muss an diese IP gebunden sein).")
                Bullet("Das App-Token steht auf dem Server in /etc/garmin-uebersicht/app-token.")
                HorizontalDivider(Modifier.padding(vertical = 8.dp))
                Text("Die Adresse und das Token bleiben nur auf diesem Gerät gespeichert.",
                    style = MaterialTheme.typography.bodySmall, color = LocalChartColors.current.muted)
            }
        }
    }
}
