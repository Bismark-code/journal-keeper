'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  BookOpen, Plus, Search, ScanText, PenLine, Tag,
  Calendar, Sparkles, Trash2, ChevronRight, Loader2,
  FileText, Upload, X, ArrowRight, Menu, Download,
  FolderOpen, Edit3, Save, ArrowLeft, Hash, Clock,
  Smile, MessageSquare, Check, Copy
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { useToast } from '@/hooks/use-toast'

// ============ API хелпер ============
const API_BASE = '/api'

async function apiFetch(path: string, options?: RequestInit) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Ошибка сервера')
  }
  return res.json()
}

// ============ Типы ============
interface JournalEntry {
  id: number
  date: string
  time: string | null
  topic: string
  mood: string
  text: string
  created_at: string
}

interface Stats {
  total_entries: number
  total_tags: number
  last_date: string | null
}

// ============ Основной компонент ============
export default function Home() {
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState('journal')
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [stats, setStats] = useState<Stats>({ total_entries: 0, total_tags: 0, last_date: null })
  const [tags, setTags] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null)

  // Загрузка данных
  const loadEntries = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch('/entries?limit=50')
      setEntries(data.entries || [])
    } catch (e: any) {
      toast({ title: 'Ошибка загрузки', description: e.message, variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [toast])

  const loadStats = useCallback(async () => {
    try {
      const data = await apiFetch('/stats')
      setStats(data)
    } catch {}
  }, [])

  const loadTags = useCallback(async () => {
    try {
      const data = await apiFetch('/tags')
      setTags(data.tags || [])
    } catch {}
  }, [])

  useEffect(() => {
    loadEntries()
    loadStats()
    loadTags()
  }, [loadEntries, loadStats, loadTags])

  const refreshAll = useCallback(() => {
    loadEntries()
    loadStats()
    loadTags()
  }, [loadEntries, loadStats, loadTags])

  // ============ Навигация ============
  const navItems = [
    { id: 'journal', label: 'Дневник', icon: BookOpen },
    { id: 'add', label: 'Новая запись', icon: Plus },
    { id: 'search', label: 'Поиск', icon: Search },
    { id: 'tags', label: 'Тэги', icon: Hash },
    { id: 'ocr', label: 'OCR', icon: ScanText },
    { id: 'editor', label: 'Редактор LLM', icon: PenLine },
    { id: 'tools', label: 'Инструменты', icon: FolderOpen },
  ]

  return (
    <div className="min-h-screen flex bg-background">
      {/* Боковая панель */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-16'} border-r bg-card transition-all duration-300 flex flex-col`}>
        <div className="p-4 border-b flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-5 h-5 text-primary-foreground" />
          </div>
          {sidebarOpen && (
            <div className="overflow-hidden">
              <h1 className="font-bold text-sm leading-tight">Дневник</h1>
              <p className="text-xs text-muted-foreground">Приватный • Локальный</p>
            </div>
          )}
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { setActiveTab(item.id); setSelectedEntry(null) }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                activeTab === item.id
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent text-muted-foreground hover:text-foreground'
              }`}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="p-2">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-accent transition-colors"
          >
            <Menu className="w-4 h-4 flex-shrink-0" />
            {sidebarOpen && <span>Свернуть</span>}
          </button>
        </div>

        {/* Статистика */}
        {sidebarOpen && (
          <div className="p-4 border-t space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Записей</span>
              <span className="font-medium">{stats.total_entries}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Тэгов</span>
              <span className="font-medium">{stats.total_tags}</span>
            </div>
            {stats.last_date && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Последняя</span>
                <span className="font-medium">{stats.last_date}</span>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* Основной контент */}
      <main className="flex-1 overflow-hidden">
        {activeTab === 'journal' && !selectedEntry && (
          <JournalView entries={entries} loading={loading} onRefresh={refreshAll} onSelect={setSelectedEntry} />
        )}
        {activeTab === 'journal' && selectedEntry && (
          <EntryDetailView entry={selectedEntry} onBack={() => { setSelectedEntry(null); refreshAll() }} />
        )}
        {activeTab === 'add' && (
          <AddEntryView onAdded={refreshAll} />
        )}
        {activeTab === 'search' && (
          <SearchView tags={tags} onSelect={setSelectedEntry} />
        )}
        {activeTab === 'tags' && (
          <TagsView tags={tags} onSelectTag={(tag) => { setActiveTab('search') }} />
        )}
        {activeTab === 'ocr' && (
          <OCRView onAdded={refreshAll} />
        )}
        {activeTab === 'editor' && (
          <EditorView />
        )}
        {activeTab === 'tools' && (
          <ToolsView onRefresh={refreshAll} />
        )}
      </main>
    </div>
  )
}

// ============ Просмотр дневника ============
function JournalView({ entries, loading, onRefresh, onSelect }: {
  entries: JournalEntry[]
  loading: boolean
  onRefresh: () => void
  onSelect: (entry: JournalEntry) => void
}) {
  const { toast } = useToast()

  const handleDelete = async (e: React.MouseEvent, date: string) => {
    e.stopPropagation()
    try {
      await apiFetch(`/entries/date/${date}`, { method: 'DELETE' })
      toast({ title: 'Удалено', description: `Записи за ${date} удалены` })
      onRefresh()
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Дневник</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {entries.length} {entries.length === 1 ? 'запись' : entries.length < 5 ? 'записи' : 'записей'}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-4">
          {loading && entries.length === 0 && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          )}

          {!loading && entries.length === 0 && (
            <div className="text-center py-20 text-muted-foreground">
              <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p className="text-lg font-medium">Дневник пуст</p>
              <p className="text-sm mt-1">Создайте первую запись</p>
            </div>
          )}

          {entries.map(entry => (
            <Card
              key={entry.id}
              className="group hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => onSelect(entry)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
                      <Calendar className="w-5 h-5 text-muted-foreground" />
                    </div>
                    <div>
                      <CardTitle className="text-base">
                        {entry.topic || 'Без темы'}
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2">
                        {entry.date}
                        {entry.time && <span>• {entry.time}</span>}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {entry.mood && (
                      <Badge variant="secondary" className="text-xs">
                        {entry.mood}
                      </Badge>
                    )}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent onClick={(e) => e.stopPropagation()}>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Удалить запись?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Все записи за {entry.date} будут удалены. Это действие нельзя отменить.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Отмена</AlertDialogCancel>
                          <AlertDialogAction onClick={(e) => handleDelete(e, entry.date)}>
                            Удалить
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap leading-relaxed line-clamp-3">
                  {entry.text}
                </p>
                <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                  <ChevronRight className="w-3 h-3" />
                  Нажмите для подробностей
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============ Детальный просмотр записи ============
function EntryDetailView({ entry, onBack }: { entry: JournalEntry; onBack: () => void }) {
  const { toast } = useToast()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(entry.text)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await apiFetch(`/entries/${entry.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: editText }),
      })
      toast({ title: 'Сохранено', description: 'Текст записи обновлён' })
      setEditing(false)
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleLLMEdit = async () => {
    setSaving(true)
    try {
      const data = await apiFetch('/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: editText }),
      })
      if (data.edited && data.edited !== data.original) {
        setEditText(data.edited)
        setEditing(true)
        toast({ title: 'Отредактировано LLM', description: 'Проверьте результат и сохраните' })
      } else {
        toast({ title: 'Без изменений', description: 'LLM вернула исходный текст' })
      }
    } catch (e: any) {
      toast({ title: 'Ошибка LLM', description: e.message, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="flex-1">
          <h2 className="text-2xl font-bold">{entry.topic || 'Без темы'}</h2>
          <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
            <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" />{entry.date}</span>
            {entry.time && <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{entry.time}</span>}
            {entry.mood && <span className="flex items-center gap-1"><Smile className="w-3.5 h-3.5" />{entry.mood}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleLLMEdit} disabled={saving}>
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            <span className="ml-1.5">LLM</span>
          </Button>
          {editing ? (
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              <span className="ml-1.5">Сохранить</span>
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Edit3 className="w-4 h-4" />
              <span className="ml-1.5">Редактировать</span>
            </Button>
          )}
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-3xl">
          {editing ? (
            <Textarea
              value={editText}
              onChange={e => setEditText(e.target.value)}
              rows={20}
              className="resize-y text-base leading-relaxed"
            />
          ) : (
            <div className="prose prose-sm max-w-none">
              <p className="whitespace-pre-wrap text-base leading-relaxed">{editText}</p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============ Добавление записи ============
function AddEntryView({ onAdded }: { onAdded: () => void }) {
  const { toast } = useToast()
  const [saving, setSaving] = useState(false)
  const [inputMode, setInputMode] = useState<'form' | 'block'>('form')
  const [form, setForm] = useState({
    date: new Date().toISOString().split('T')[0],
    time: new Date().toTimeString().slice(0, 5),
    topic: '',
    mood: '',
    text: '',
    tags: '',
  })
  const [rawBlock, setRawBlock] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (inputMode === 'block') {
      if (!rawBlock.trim()) {
        toast({ title: 'Ошибка', description: 'Вставьте блок ===...===', variant: 'destructive' })
        return
      }
      // Отправляем текст блока как обычную запись, парсим на бэкенде
      setSaving(true)
      try {
        // Простой парсинг блока на фронтенде
        const lines = rawBlock.trim().split('\n')
        let date = new Date().toISOString().split('T')[0]
        let time = ''
        let topic = ''
        let mood = ''
        let text = ''
        let tags: string[] = []
        let inText = false

        for (const line of lines) {
          const trimmed = line.trim()
          if (trimmed.match(/^===+$/)) continue
          const dateM = trimmed.match(/^ДАТА:\s*(.+)$/i)
          const timeM = trimmed.match(/^ВРЕМЯ:\s*(.+)$/i)
          const topicM = trimmed.match(/^ТЕМА:\s*(.+)$/i)
          const moodM = trimmed.match(/^НАСТРОЕНИЕ:\s*(.+)$/i)
          const tagsM = trimmed.match(/^ТЭГИ:\s*(.+)$/i) || trimmed.match(/^ТЕГИ:\s*(.+)$/i)
          const textM = trimmed.match(/^ТЕКСТ:\s*(.*)$/i)

          if (dateM) { date = dateM[1].trim(); inText = false }
          else if (timeM) { time = timeM[1].trim(); inText = false }
          else if (topicM) { topic = topicM[1].trim(); inText = false }
          else if (moodM) { mood = moodM[1].trim(); inText = false }
          else if (tagsM) { tags = tagsM[1].split(/[,;]+/).map(t => t.trim().toLowerCase()).filter(Boolean); inText = false }
          else if (textM) { text = textM[1]; inText = true }
          else if (inText) { text += '\n' + trimmed }
        }

        if (!text.trim()) {
          toast({ title: 'Ошибка', description: 'Не найден ТЕКСТ в блоке', variant: 'destructive' })
          setSaving(false)
          return
        }

        await apiFetch('/entries', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ date, time: time || null, topic, mood, text, tags }),
        })

        toast({ title: 'Готово', description: 'Запись из блока добавлена' })
        setRawBlock('')
        onAdded()
      } catch (e: any) {
        toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
      } finally {
        setSaving(false)
      }
      return
    }

    if (!form.text.trim()) {
      toast({ title: 'Ошибка', description: 'Текст записи не может быть пустым', variant: 'destructive' })
      return
    }

    setSaving(true)
    try {
      const tagsList = form.tags
        .split(/[,;]+/)
        .map(t => t.trim().toLowerCase())
        .filter(Boolean)

      await apiFetch('/entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: form.date,
          time: form.time || null,
          topic: form.topic,
          mood: form.mood,
          text: form.text,
          tags: tagsList,
        }),
      })

      toast({ title: 'Готово', description: 'Запись добавлена' })
      setForm({
        date: new Date().toISOString().split('T')[0],
        time: new Date().toTimeString().slice(0, 5),
        topic: '',
        mood: '',
        text: '',
        tags: '',
      })
      onAdded()
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b">
        <h2 className="text-2xl font-bold">Новая запись</h2>
        <p className="text-sm text-muted-foreground mt-1">Создайте запись в дневнике</p>
      </div>

      <ScrollArea className="flex-1">
        <form onSubmit={handleSubmit} className="p-6 max-w-2xl space-y-6">
          {/* Переключатель режима ввода */}
          <div className="flex gap-2">
            <Button
              type="button"
              variant={inputMode === 'form' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setInputMode('form')}
            >
              Форма
            </Button>
            <Button
              type="button"
              variant={inputMode === 'block' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setInputMode('block')}
            >
              Блок ===...===
            </Button>
          </div>

          {inputMode === 'form' ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="date">Дата</Label>
                  <Input
                    id="date"
                    type="date"
                    value={form.date}
                    onChange={e => setForm({ ...form, date: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="time">Время</Label>
                  <Input
                    id="time"
                    type="time"
                    value={form.time}
                    onChange={e => setForm({ ...form, time: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="topic">Тема</Label>
                <Input
                  id="topic"
                  placeholder="О чём эта запись?"
                  value={form.topic}
                  onChange={e => setForm({ ...form, topic: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="mood">Настроение</Label>
                  <Input
                    id="mood"
                    placeholder="например: задумчивое"
                    value={form.mood}
                    onChange={e => setForm({ ...form, mood: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tags">Тэги</Label>
                  <Input
                    id="tags"
                    placeholder="через запятую"
                    value={form.tags}
                    onChange={e => setForm({ ...form, tags: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="text">Текст записи</Label>
                <Textarea
                  id="text"
                  placeholder="Что сегодня на душе?"
                  value={form.text}
                  onChange={e => setForm({ ...form, text: e.target.value })}
                  rows={8}
                  className="resize-y"
                  required
                />
              </div>
            </>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="rawblock">Вставьте блок в формате ===...===</Label>
              <Textarea
                id="rawblock"
                placeholder={`===\nДАТА: 2026-05-10\nВРЕМЯ: 14:30\nТЕМА: Мои мысли\nТЭГИ: личное, дневник\nНАСТРОЕНИЕ: спокойное\nТЕКСТ:\nСегодня хороший день...\n==="`}
                value={rawBlock}
                onChange={e => setRawBlock(e.target.value)}
                rows={12}
                className="resize-y font-mono text-sm"
              />
            </div>
          )}

          <Button type="submit" disabled={saving} className="w-full">
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                Сохранение...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Добавить запись
              </>
            )}
          </Button>
        </form>
      </ScrollArea>
    </div>
  )
}

// ============ Поиск ============
function SearchView({ tags, onSelect }: { tags: string[]; onSelect: (entry: JournalEntry) => void }) {
  const { toast } = useToast()
  const [searchMode, setSearchMode] = useState<'text' | 'tag' | 'date'>('text')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<JournalEntry[]>([])
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    setSearched(true)
    try {
      let endpoint = ''
      if (searchMode === 'text') {
        endpoint = `/search/text?q=${encodeURIComponent(query)}`
      } else if (searchMode === 'tag') {
        endpoint = `/search/tag?tag=${encodeURIComponent(query)}`
      } else {
        endpoint = `/search/date?date=${encodeURIComponent(query)}`
      }
      const data = await apiFetch(endpoint)
      setResults(data.entries || [])
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b">
        <h2 className="text-2xl font-bold">Поиск</h2>
        <p className="text-sm text-muted-foreground mt-1">Ищите по тексту, тэгам или дате</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-2xl space-y-6">
          {/* Переключатель режима */}
          <div className="flex gap-2">
            {[
              { mode: 'text' as const, label: 'По тексту', icon: Search },
              { mode: 'tag' as const, label: 'По тэгу', icon: Tag },
              { mode: 'date' as const, label: 'По дате', icon: Calendar },
            ].map(item => (
              <Button
                key={item.mode}
                variant={searchMode === item.mode ? 'default' : 'outline'}
                size="sm"
                onClick={() => { setSearchMode(item.mode); setQuery(''); setSearched(false) }}
              >
                <item.icon className="w-4 h-4 mr-1" />
                {item.label}
              </Button>
            ))}
          </div>

          {/* Поле ввода */}
          <div className="flex gap-2">
            {searchMode === 'date' ? (
              <Input
                type="date"
                value={query}
                onChange={e => setQuery(e.target.value)}
                className="flex-1"
              />
            ) : (
              <Input
                placeholder={
                  searchMode === 'text'
                    ? 'Введите текст для поиска...'
                    : 'Введите тэг...'
                }
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                className="flex-1"
              />
            )}
            <Button onClick={handleSearch} disabled={searching || !query.trim()}>
              {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            </Button>
          </div>

          {/* Быстрые тэги */}
          {searchMode === 'tag' && tags.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Быстрый выбор:</Label>
              <div className="flex flex-wrap gap-2">
                {tags.map(tag => (
                  <Badge
                    key={tag}
                    variant="outline"
                    className="cursor-pointer hover:bg-accent transition-colors"
                    onClick={() => { setQuery(tag); }}
                  >
                    #{tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Результаты */}
          {searched && (
            <div className="space-y-4">
              <Separator />
              <p className="text-sm text-muted-foreground">
                Найдено: {results.length} {results.length === 1 ? 'запись' : results.length < 5 ? 'записи' : 'записей'}
              </p>
              {results.map(entry => (
                <Card
                  key={entry.id}
                  className="hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => onSelect(entry)}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm">{entry.topic || 'Без темы'}</CardTitle>
                      <span className="text-xs text-muted-foreground">{entry.date}</span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm whitespace-pre-wrap line-clamp-3">{entry.text}</p>
                    {entry.mood && (
                      <Badge variant="secondary" className="mt-2 text-xs">{entry.mood}</Badge>
                    )}
                  </CardContent>
                </Card>
              ))}
              {results.length === 0 && (
                <p className="text-center text-muted-foreground py-8">Ничего не найдено</p>
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============ Тэги ============
function TagsView({ tags, onSelectTag }: { tags: string[]; onSelectTag: (tag: string) => void }) {
  const [tagCounts, setTagCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    async function loadCounts() {
      const counts: Record<string, number> = {}
      for (const tag of tags) {
        try {
          const data = await apiFetch(`/search/tag?tag=${encodeURIComponent(tag)}`)
          counts[tag] = data.entries?.length || 0
        } catch {
          counts[tag] = 0
        }
      }
      setTagCounts(counts)
    }
    if (tags.length > 0) loadCounts()
  }, [tags])

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b">
        <h2 className="text-2xl font-bold">Тэги</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {tags.length} {tags.length === 1 ? 'тэг' : tags.length < 5 ? 'тэга' : 'тэгов'}
        </p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6">
          {tags.length === 0 ? (
            <div className="text-center py-20 text-muted-foreground">
              <Hash className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p className="text-lg font-medium">Тэгов пока нет</p>
              <p className="text-sm mt-1">Они появятся при добавлении записей</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {tags.map(tag => (
                <Card
                  key={tag}
                  className="hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => onSelectTag(tag)}
                >
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Hash className="w-4 h-4 text-primary" />
                      <span className="font-medium text-sm">{tag}</span>
                    </div>
                    <Badge variant="secondary" className="text-xs">
                      {tagCounts[tag] ?? '...'}
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============ OCR ============
function OCRView({ onAdded }: { onAdded: () => void }) {
  const { toast } = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [recognizing, setRecognizing] = useState(false)
  const [recognizedText, setRecognizedText] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveForm, setSaveForm] = useState({
    date: new Date().toISOString().split('T')[0],
    topic: '',
    mood: '',
    tags: '',
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setRecognizedText('')
      const reader = new FileReader()
      reader.onload = (ev) => setPreview(ev.target?.result as string)
      reader.readAsDataURL(f)
    }
  }

  const handleRecognize = async () => {
    if (!file) return
    setRecognizing(true)
    setRecognizedText('')
    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch('/api/ocr', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setRecognizedText(data.text || '')
      if (!data.text) {
        toast({ title: 'Не распознано', description: 'Текст не найден на изображении', variant: 'destructive' })
      } else {
        toast({ title: 'Распознано', description: 'Текст извлечён из изображения' })
      }
    } catch (e: any) {
      toast({ title: 'Ошибка OCR', description: e.message, variant: 'destructive' })
    } finally {
      setRecognizing(false)
    }
  }

  const handleSave = async () => {
    if (!recognizedText.trim()) return
    setSaving(true)
    try {
      const tagsList = saveForm.tags
        .split(/[,;]+/)
        .map(t => t.trim().toLowerCase())
        .filter(Boolean)

      await apiFetch('/entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: saveForm.date,
          topic: saveForm.topic,
          mood: saveForm.mood,
          text: recognizedText,
          tags: tagsList,
        }),
      })
      toast({ title: 'Сохранено', description: 'Запись из OCR добавлена' })
      setRecognizedText('')
      setFile(null)
      setPreview(null)
      onAdded()
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b">
        <h2 className="text-2xl font-bold">OCR — Распознавание</h2>
        <p className="text-sm text-muted-foreground mt-1">Загрузите фото рукописного текста</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-3xl space-y-6">
          {/* Загрузка файла */}
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="border-2 border-dashed rounded-lg p-8 text-center">
                  {preview ? (
                    <div className="space-y-4">
                      <img src={preview} alt="Preview" className="max-h-64 mx-auto rounded-lg" />
                      <Button variant="ghost" size="sm" onClick={() => { setFile(null); setPreview(null); setRecognizedText('') }}>
                        <X className="w-4 h-4 mr-1" /> Убрать
                      </Button>
                    </div>
                  ) : (
                    <div>
                      <Upload className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                      <p className="text-sm text-muted-foreground mb-3">Выберите изображение</p>
                      <Label htmlFor="ocr-file" className="cursor-pointer">
                        <Input
                          id="ocr-file"
                          type="file"
                          accept="image/*"
                          onChange={handleFileChange}
                          className="hidden"
                        />
                        <Button variant="outline" asChild>
                          <span>Выбрать файл</span>
                        </Button>
                      </Label>
                    </div>
                  )}
                </div>

                {file && (
                  <Button onClick={handleRecognize} disabled={recognizing} className="w-full">
                    {recognizing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Распознаю...
                      </>
                    ) : (
                      <>
                        <ScanText className="w-4 h-4 mr-2" />
                        Распознать текст
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Результат распознавания */}
          {recognizedText && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Распознанный текст</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  value={recognizedText}
                  onChange={e => setRecognizedText(e.target.value)}
                  rows={6}
                  className="resize-y"
                />

                <Separator />

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Дата</Label>
                    <Input
                      type="date"
                      value={saveForm.date}
                      onChange={e => setSaveForm({ ...saveForm, date: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Тема</Label>
                    <Input
                      placeholder="Тема записи"
                      value={saveForm.topic}
                      onChange={e => setSaveForm({ ...saveForm, topic: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Настроение</Label>
                    <Input
                      placeholder="Настроение"
                      value={saveForm.mood}
                      onChange={e => setSaveForm({ ...saveForm, mood: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Тэги</Label>
                    <Input
                      placeholder="через запятую"
                      value={saveForm.tags}
                      onChange={e => setSaveForm({ ...saveForm, tags: e.target.value })}
                    />
                  </div>
                </div>

                <Button onClick={handleSave} disabled={saving} className="w-full">
                  {saving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Сохранение...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4 mr-2" />
                      Сохранить как запись
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============ LLM Редактор ============
function EditorView() {
  const { toast } = useToast()
  const [originalText, setOriginalText] = useState('')
  const [editedText, setEditedText] = useState('')
  const [editing, setEditing] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleEdit = async () => {
    if (!originalText.trim()) return
    setEditing(true)
    setEditedText('')
    try {
      const data = await apiFetch('/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: originalText }),
      })
      setEditedText(data.edited || originalText)
      if (data.edited === data.original) {
        toast({ title: 'Без изменений', description: 'LLM недоступна — текст возвращён без изменений' })
      } else {
        toast({ title: 'Отредактировано', description: 'Текст обработан LLM' })
      }
    } catch (e: any) {
      toast({ title: 'Ошибка', description: e.message, variant: 'destructive' })
    } finally {
      setEditing(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(editedText)
    setCopied(true)
    toast({ title: 'Скопировано', description: 'Текст скопирован в буфер обмена' })
    setTimeout(() => setCopied(false), 2000)
  }

  const handleReplace = () => {
    setOriginalText(editedText)
    setEditedText('')
    toast({ title: 'Заменено', description: 'Исходный текст заменён результатом' })
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b">
        <h2 className="text-2xl font-bold">LLM Редактор</h2>
        <p className="text-sm text-muted-foreground mt-1">Улучшите текст записи через Ollama</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-3xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <PenLine className="w-4 h-4" />
                Исходный текст
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="Вставьте текст для редактирования..."
                value={originalText}
                onChange={e => setOriginalText(e.target.value)}
                rows={8}
                className="resize-y"
              />
              <Button onClick={handleEdit} disabled={editing || !originalText.trim()} className="w-full">
                {editing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Редактирую...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Отредактировать
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {editedText && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    Результат
                  </CardTitle>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleCopy}>
                      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleReplace}>
                      Заменить исходный
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={editedText}
                  onChange={e => setEditedText(e.target.value)}
                  rows={8}
                  className="resize-y"
                />
              </CardContent>
            </Card>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============ Инструменты (Импорт/Экспорт) ============
function ToolsView({ onRefresh }: { onRefresh: () => void }) {
  const { toast } = useToast()
  const [importPath, setImportPath] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<any>(null)
  const [exporting, setExporting] = useState(false)

  const handleImport = async () => {
    if (!importPath.trim()) return
    setImporting(true)
    setImportResult(null)
    try {
      const data = await apiFetch(`/import?folder=${encodeURIComponent(importPath)}`, {
        method: 'POST',
      })
      setImportResult(data)
      toast({ title: 'Импорт завершён', description: `Добавлено: ${data.added}, дубликатов: ${data.duplicates}` })
      onRefresh()
    } catch (e: any) {
      toast({ title: 'Ошибка импорта', description: e.message, variant: 'destructive' })
    } finally {
      setImporting(false)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const data = await apiFetch('/export')
      const content = data.entries?.join('\n\n') || ''
      if (!content) {
        toast({ title: 'Пусто', description: 'Нет записей для экспорта' })
        return
      }
      // Скачиваем файл
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `journal_export_${new Date().toISOString().split('T')[0]}.txt`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast({ title: 'Экспортировано', description: `${data.count} записей сохранено` })
    } catch (e: any) {
      toast({ title: 'Ошибка экспорта', description: e.message, variant: 'destructive' })
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b">
        <h2 className="text-2xl font-bold">Инструменты</h2>
        <p className="text-sm text-muted-foreground mt-1">Импорт и экспорт записей</p>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 max-w-2xl space-y-6">
          {/* Экспорт */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Download className="w-4 h-4" />
                Экспорт записей
              </CardTitle>
              <CardDescription>
                Скачать все записи в формате ===...===
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={handleExport} disabled={exporting} className="w-full">
                {exporting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Экспортирую...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Экспортировать все записи
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Импорт */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FolderOpen className="w-4 h-4" />
                Импорт архива
              </CardTitle>
              <CardDescription>
                Загрузить записи из папки с .txt файлами (формат ===...===)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Путь к папке архива</Label>
                <Input
                  placeholder="/home/user/diary_archive"
                  value={importPath}
                  onChange={e => setImportPath(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Укажите абсолютный путь к папке на сервере
                </p>
              </div>
              <Button onClick={handleImport} disabled={importing || !importPath.trim()} className="w-full">
                {importing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Импортирую...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Импортировать
                  </>
                )}
              </Button>

              {importResult && (
                <div className="bg-muted rounded-lg p-4 space-y-1 text-sm">
                  <p><strong>Файлов найдено:</strong> {importResult.files_found}</p>
                  <p><strong>Блоков найдено:</strong> {importResult.blocks_found}</p>
                  <p><strong>Добавлено:</strong> {importResult.added}</p>
                  <p><strong>Дубликатов:</strong> {importResult.duplicates}</p>
                  <p><strong>Невалидных:</strong> {importResult.invalid}</p>
                  {importResult.errors?.length > 0 && (
                    <p className="text-destructive">Ошибок: {importResult.errors.length}</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </div>
  )
}
