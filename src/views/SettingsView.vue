<script setup>
import { ref, computed } from 'vue'
import { useSettingsStore } from '../stores/settings'

const s = useSettingsStore()

const THEMES = [
  { v: 'light',  label: '日間', hint: '亮色背景' },
  { v: 'dark',   label: '夜間', hint: '暗色背景' },
  { v: 'system', label: '跟隨系統', hint: '依作業系統設定切換' },
]

const FONT_SIZES = [
  { v: 'compact', label: '小', hint: '14px 基準' },
  { v: 'normal',  label: '標準', hint: '16px 基準' },
  { v: 'large',   label: '大', hint: '18px 基準' },
]

const PROVIDERS = [
  { v: 'anthropic', label: 'Anthropic Claude', model: s.PROVIDER_DEFAULT_MODELS.anthropic, signup: 'https://console.anthropic.com/settings/keys' },
  { v: 'openai',    label: 'OpenAI',           model: s.PROVIDER_DEFAULT_MODELS.openai,    signup: 'https://platform.openai.com/api-keys' },
  { v: 'google',    label: 'Google Gemini',    model: s.PROVIDER_DEFAULT_MODELS.google,    signup: 'https://aistudio.google.com/apikey' },
]

const showKey = ref({ anthropic: false, openai: false, google: false })

const savedHint = ref('')
function flashSaved() {
  savedHint.value = '已儲存'
  setTimeout(() => { savedHint.value = '' }, 1200)
}

function clearKey(provider) {
  s.apiKeys[provider] = ''
  flashSaved()
}

const currentDefaultModel = computed(() => s.PROVIDER_DEFAULT_MODELS[s.llmProvider])
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold tracking-tight mb-1">設定</h1>
    <p class="text-sm text-slate-500 mb-5">所有設定僅儲存在你的瀏覽器（localStorage），不會上傳。</p>

    <!-- 主題 -->
    <section class="mb-5 bg-white border border-[#e7e7e1] p-4">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">外觀</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">主題</h2>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="t in THEMES" :key="t.v"
          @click="s.theme = t.v"
          :class="[
            'p-3 border text-sm transition text-left',
            s.theme === t.v
              ? 'bg-[#0a0e16] text-white border-[#0a0e16]'
              : 'bg-white border-[#d8d8d2] hover:border-[#0a0e16]',
          ]"
        >
          <div class="font-semibold">{{ t.label }}</div>
          <div class="text-[11px] opacity-70 mt-0.5">{{ t.hint }}</div>
        </button>
      </div>
    </section>

    <!-- 字體 -->
    <section class="mb-5 bg-white border border-[#e7e7e1] p-4">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">外觀</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">字體大小</h2>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="f in FONT_SIZES" :key="f.v"
          @click="s.fontSize = f.v"
          :class="[
            'p-3 border transition text-left',
            s.fontSize === f.v
              ? 'bg-[#0a0e16] text-white border-[#0a0e16]'
              : 'bg-white border-[#d8d8d2] hover:border-[#0a0e16]',
          ]"
        >
          <div class="font-semibold" :class="{
            'text-sm': f.v === 'compact',
            'text-base': f.v === 'normal',
            'text-lg': f.v === 'large',
          }">{{ f.label }} Aa</div>
          <div class="text-[11px] opacity-70 mt-0.5">{{ f.hint }}</div>
        </button>
      </div>
      <p class="text-[11px] text-slate-500 mt-2 leading-snug">
        會同時影響全站所有文字與間距（基於 rem）。
      </p>
    </section>

    <!-- LLM 摘要 -->
    <section class="mb-5 bg-white border border-[#e7e7e1] p-4">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">個股摘要</div>
      <h2 class="text-lg font-semibold tracking-tight mb-1">LLM 供應商與 API key</h2>
      <p class="text-xs text-slate-600 mb-4 leading-relaxed">
        在個股頁手動觸發摘要產生。請求由你的瀏覽器直接呼叫供應商 API，
        <strong>金鑰只存在你這台裝置的 localStorage</strong>，本站沒有後端、不會收集。
      </p>

      <!-- 供應商選擇 -->
      <label class="block text-xs font-semibold text-slate-700 mb-1.5">使用的供應商</label>
      <div class="grid grid-cols-3 gap-2 mb-4">
        <button
          v-for="p in PROVIDERS" :key="p.v"
          @click="s.llmProvider = p.v"
          :class="[
            'p-2 border text-xs transition text-left',
            s.llmProvider === p.v
              ? 'bg-[#0a0e16] text-white border-[#0a0e16]'
              : 'bg-white border-[#d8d8d2] hover:border-[#0a0e16]',
          ]"
        >
          <div class="font-semibold">{{ p.label }}</div>
          <div class="text-[10px] opacity-70 font-mono mt-0.5 truncate">{{ p.model }}</div>
        </button>
      </div>

      <!-- 模型自訂 -->
      <label class="block text-xs font-semibold text-slate-700 mb-1.5">
        模型（留空使用預設 <span class="font-mono text-slate-500">{{ currentDefaultModel }}</span>）
      </label>
      <input
        v-model="s.llmModel"
        type="text"
        :placeholder="currentDefaultModel"
        class="w-full mb-4 px-3 py-1.5 border border-[#d8d8d2] bg-white text-sm focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] transition"
      />

      <!-- API keys（三家分開） -->
      <div v-for="p in PROVIDERS" :key="`key-${p.v}`" class="mb-3">
        <div class="flex items-baseline justify-between mb-1">
          <label class="block text-xs font-semibold text-slate-700">
            {{ p.label }} API Key
            <span v-if="s.apiKeys[p.v]" class="ml-1 text-[10px] text-emerald-600 font-mono uppercase tracking-wider">已設定</span>
          </label>
          <a :href="p.signup" target="_blank" rel="noopener" class="text-[11px] text-[#b4530b] hover:text-[#0a0e16]">取得 key ↗</a>
        </div>
        <div class="flex gap-2">
          <input
            v-model="s.apiKeys[p.v]"
            @input="flashSaved"
            :type="showKey[p.v] ? 'text' : 'password'"
            placeholder="sk-..."
            spellcheck="false"
            autocomplete="off"
            class="flex-1 px-3 py-1.5 border border-[#d8d8d2] bg-white text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] transition"
          />
          <button
            @click="showKey[p.v] = !showKey[p.v]"
            class="px-2 py-1.5 border border-[#d8d8d2] text-xs hover:bg-slate-50 transition"
            :title="showKey[p.v] ? '隱藏' : '顯示'"
          >{{ showKey[p.v] ? '隱藏' : '顯示' }}</button>
          <button
            v-if="s.apiKeys[p.v]"
            @click="clearKey(p.v)"
            class="px-2 py-1.5 border border-[#d8d8d2] text-xs hover:bg-red-50 hover:border-red-300 hover:text-red-600 transition"
          >清除</button>
        </div>
      </div>

      <p class="text-[11px] text-slate-500 mt-3 leading-relaxed border-l-2 border-amber-400 pl-3">
        本站沒有後端伺服器，無法替你保管金鑰也無法代為呼叫 API。請只在自己常用的裝置設定，且勿把金鑰貼到公用電腦。
      </p>
    </section>

    <!-- 重設 -->
    <div class="flex items-center gap-3">
      <button
        @click="s.reset()"
        class="px-3 py-1.5 border border-[#d8d8d2] text-xs hover:bg-red-50 hover:border-red-300 hover:text-red-600 transition"
      >重設所有設定</button>
      <span v-if="savedHint" class="text-xs text-emerald-600 font-mono">{{ savedHint }} ✓</span>
    </div>
  </div>
</template>
