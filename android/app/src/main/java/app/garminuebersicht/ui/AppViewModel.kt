package app.garminuebersicht.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import app.garminuebersicht.data.Activity
import app.garminuebersicht.data.Api
import app.garminuebersicht.data.Coach
import app.garminuebersicht.data.Night
import app.garminuebersicht.data.Overview
import app.garminuebersicht.data.Settings
import app.garminuebersicht.data.Status
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class UiState(
    val loading: Boolean = false,
    val error: String? = null,
    val status: Status? = null,
    val coach: Coach? = null,
    val days: Int = 30,
    val overview: Overview? = null,
    val activities: List<Activity> = emptyList(),
    val nights: List<Night> = emptyList(),
    val syncRequested: Boolean = false,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {
    val settings = Settings(app)
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state
    private var loadJob: Job? = null

    private fun api() = Api(settings.serverUrl, settings.token)

    init {
        if (settings.configured) refresh()
    }

    fun setDays(days: Int) {
        if (days == _state.value.days) return
        _state.update { it.copy(days = days) }
        refresh()
    }

    fun refresh() {
        loadJob?.cancel()
        loadJob = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val api = api()
                val days = _state.value.days
                // coroutineScope: Scheitert ein Abruf, kommt der Fehler hier im catch an,
                // statt die übergeordnete Coroutine (und damit die App) abstürzen zu lassen.
                coroutineScope {
                    val status = async { api.status() }
                    val coach = async { api.coach() }
                    val overview = async { api.overview(days) }
                    val acts = async { api.activities(days) }
                    val nights = async { api.sleep(days) }
                    val loaded = UiState(status = status.await(), coach = coach.await(), overview = overview.await(),
                        activities = acts.await(), nights = nights.await())
                    _state.update {
                        it.copy(loading = false, status = loaded.status, coach = loaded.coach, overview = loaded.overview,
                            activities = loaded.activities, nights = loaded.nights)
                    }
                }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: e.toString()) }
            }
        }
    }

    /** Abgleich mit Garmin auf dem Server anstoßen und warten, bis er fertig ist. */
    fun syncNow() {
        viewModelScope.launch {
            _state.update { it.copy(syncRequested = true, error = null) }
            try {
                val api = api()
                api.triggerSync()
                delay(1500)
                for (attempt in 0 until 120) { // höchstens ~6 Minuten (erster Abgleich lädt ein ganzes Jahr)
                    val st = api.status()
                    _state.update { it.copy(status = st) }
                    if (!st.syncing) break
                    delay(3000)
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message ?: e.toString()) }
            } finally {
                _state.update { it.copy(syncRequested = false) }
                refresh()
            }
        }
    }

    fun saveSettings(url: String, token: String) {
        settings.serverUrl = url
        settings.token = token
        _state.value = UiState(days = _state.value.days)
        refresh()
    }

    /** Verbindung prüfen, ohne die gespeicherten Einstellungen zu ändern. */
    suspend fun testConnection(url: String, token: String): Result<Status> =
        runCatching { Api(url.trim().trimEnd('/'), token.trim()).status() }
}
