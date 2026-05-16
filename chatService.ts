import { join, dirname, basename, extname } from 'path'
import { existsSync, mkdirSync, readdirSync, statSync, readFileSync, writeFileSync, copyFileSync, unlinkSync, watch, promises as fsPromises } from 'fs'
import * as path from 'path'
import * as fs from 'fs'
import * as https from 'https'
import * as http from 'http'
import * as fzstd from 'fzstd'
import * as crypto from 'crypto'
import { app, BrowserWindow, dialog } from 'electron'
import { ConfigService } from './config'
import { wcdbService } from './wcdbService'
import { MessageCacheService } from './messageCacheService'
import { ContactCacheService, ContactCacheEntry } from './contactCacheService'
import { SessionStatsCacheService, SessionStatsCacheEntry, SessionStatsCacheStats } from './sessionStatsCacheService'
import { GroupMyMessageCountCacheService, GroupMyMessageCountCacheEntry } from './groupMyMessageCountCacheService'
import { exportCardDiagnosticsService } from './exportCardDiagnosticsService'
import { voiceTranscribeService } from './voiceTranscribeService'
import { ImageDecryptService } from './imageDecryptService'
import { CONTACT_REGION_LOOKUP_DATA } from './contactRegionLookupData'
import { LRUCache } from '../utils/LRUCache.js'

export interface ChatSession {
  username: string
  type: number
  unreadCount: number
  summary: string
  sortTimestamp: number  // 用于排序
  lastTimestamp: number  // 用于显示时间
  lastMsgType: number
  messageCountHint?: number
  displayName?: string
  avatarUrl?: string
  lastMsgSender?: string
  lastSenderDisplayName?: string
  selfWxid?: string
  isFolded?: boolean  // 是否已折叠进"折叠的群聊"
  isMuted?: boolean   // 是否开启免打扰
}

export interface Message {
  messageKey: string
  localId: number
  serverId: number
  serverIdRaw?: string
  localType: number
  createTime: number
  sortSeq: number
  isSend: number | null
  senderUsername: string | null
  parsedContent: string
  rawContent: string
  content?: string  // 原始XML内容（与rawContent相同，供前端使用）
  // 表情包相关
  emojiCdnUrl?: string
  emojiMd5?: string
  emojiLocalPath?: string  // 本地缓存 castle 路径
  emojiThumbUrl?: string
  emojiEncryptUrl?: string
  emojiAesKey?: string
  // 引用消息相关
  quotedContent?: string
  quotedSender?: string
  // 图片/视频相关
  imageMd5?: string
  imageDatName?: string
  videoMd5?: string
  aesKey?: string
  encrypVer?: number
  cdnThumbUrl?: string
  voiceDurationSeconds?: number
  // Type 49 细分字段
  linkTitle?: string        // 链接/文件标题
  linkUrl?: string          // 链接 URL
  linkThumb?: string        // 链接缩略图
  fileName?: string         // 文件名
  fileSize?: number         // 文件大小
  fileExt?: string          // 文件扩展名
  fileMd5?: string          // 文件 MD5
  xmlType?: string          // XML 中的 type 字段
  appMsgKind?: string       // 归一化 appmsg 类型
  appMsgDesc?: string
  appMsgAppName?: string
  appMsgSourceName?: string
  appMsgSourceUsername?: string
  appMsgThumbUrl?: string
  appMsgMusicUrl?: string
  appMsgDataUrl?: string
  appMsgLocationLabel?: string
  finderNickname?: string
  finderUsername?: string
  finderCoverUrl?: string
  finderAvatar?: string
  finderDuration?: number
  // 位置消息
  locationLat?: number
  locationLng?: number
  locationPoiname?: string
  locationLabel?: string
  // 音乐消息
  musicAlbumUrl?: string
  musicUrl?: string
  // 礼物消息
  giftImageUrl?: string
  giftWish?: string
  giftPrice?: string
  // 名片消息
  cardUsername?: string     // 名片的微信ID
  cardNickname?: string     // 名片的昵称
  cardAvatarUrl?: string    // 名片头像 URL
  // 转账消息
  transferPayerUsername?: string   // 转账付款人
  transferReceiverUsername?: string // 转账收款人
  // 聊天记录
  chatRecordTitle?: string  // 聊天记录标题
  chatRecordList?: Array<{
    datatype: number
    sourcename: string
    sourcetime: string
    sourceheadurl?: string
    datadesc?: string
    datatitle?: string
    fileext?: string
    datasize?: number
    messageuuid?: string
    dataurl?: string
    datathumburl?: string
    datacdnurl?: string
    cdndatakey?: string
    cdnthumbkey?: string
    aeskey?: string
    md5?: string
    fullmd5?: string
    thumbfullmd5?: string
    srcMsgLocalid?: number
    imgheight?: number
    imgwidth?: number
    duration?: number
    chatRecordTitle?: string
    chatRecordDesc?: string
    chatRecordList?: any[]
  }>
  _db_path?: string // 内部字段：记录消息所属数据库路径
}

type ResourceMessageType = 'image' | 'video' | 'voice' | 'file'

interface ResourceMessageItem extends Message {
  sessionId: string
  sessionDisplayName?: string
  resourceType: ResourceMessageType
}

export interface Contact {
  username: string
  alias: string
  remark: string
  nickName: string
}

export interface ContactInfo {
  username: string
  displayName: string
  remark?: string
  nickname?: string
  alias?: string
  labels?: string[]
  detailDescription?: string
  region?: string
  avatarUrl?: string
  type: 'friend' | 'group' | 'official' | 'former_friend' | 'other'
}

interface GetContactsOptions {
  lite?: boolean
}

interface ExportSessionStats {
  totalMessages: number
  voiceMessages: number
  imageMessages: number
  videoMessages: number
  emojiMessages: number
  transferMessages: number
  redPacketMessages: number
  callMessages: number
  firstTimestamp?: number
  lastTimestamp?: number
  privateMutualGroups?: number
  groupMemberCount?: number
  groupMyMessages?: number
  groupActiveSpeakers?: number
  groupMutualFriends?: number
}

interface ExportSessionStatsOptions {
  includeRelations?: boolean
  forceRefresh?: boolean
  allowStaleCache?: boolean
  preferAccurateSpecialTypes?: boolean
  cacheOnly?: boolean
  beginTimestamp?: number
  endTimestamp?: number
}

interface ExportSessionStatsCacheMeta {
  updatedAt: number
  stale: boolean
  includeRelations: boolean
  source: 'memory' | 'disk' | 'fresh'
}

interface ExportTabCounts {
  private: number
  group: number
  official: number
  former_friend: number
}

interface SessionDetailFast {
  wxid: string
  displayName: string
  remark?: string
  nickName?: string
  alias?: string
  avatarUrl?: string
  messageCount: number
}

interface SessionDetailExtra {
  firstMessageTime?: number
  latestMessageTime?: number
  messageTables: { dbName: string; tableName: string; count: number }[]
}

type SessionDetail = SessionDetailFast & SessionDetailExtra

interface SyntheticUnreadState {
  readTimestamp: number
  scannedTimestamp: number
  latestTimestamp: number
  unreadCount: number
  summaryTimestamp?: number
  summary?: string
  lastMsgType?: number
}

interface MyFootprintSummary {
  private_inbound_people: number
  private_replied_people: number
  private_outbound_people: number
  private_reply_rate: number
  mention_count: number
  mention_group_count: number
}

interface MyFootprintPrivateSession {
  session_id: string
  incoming_count: number
  outgoing_count: number
  replied: boolean
  first_incoming_ts: number
  first_reply_ts: number
  latest_ts: number
  anchor_local_id: number
  anchor_create_time: number
  displayName?: string
  avatarUrl?: string
}

interface MyFootprintPrivateSegment {
  session_id: string
  segment_index: number
  start_ts: number
  end_ts: number
  duration_sec: number
  incoming_count: number
  outgoing_count: number
  message_count: number
  replied: boolean
  first_incoming_ts: number
  first_reply_ts: number
  latest_ts: number
  anchor_local_id: number
  anchor_create_time: number
  displayName?: string
  avatarUrl?: string
}

interface MyFootprintMentionItem {
  session_id: string
  local_id: number
  create_time: number
  sender_username: string
  message_content: string
  source: string
  sessionDisplayName?: string
  senderDisplayName?: string
  senderAvatarUrl?: string
}

interface MyFootprintMentionGroup {
  session_id: string
  count: number
  latest_ts: number
  displayName?: string
  avatarUrl?: string
}

interface MyFootprintDiagnostics {
  truncated: boolean
  scanned_dbs: number
  elapsed_ms: number
  mention_truncated?: boolean
  private_truncated?: boolean
  native_ms?: number
  source_filter_ms?: number
  fallback_ms?: number
  enrich_ms?: number
  pipeline_ms?: number
  fallback_used?: boolean
  private_limit_effective?: number
  mention_candidate_limit?: number
  native_mention_candidates?: number
  source_filtered_mentions?: number
  private_session_count?: number
  group_session_count?: number
  native_passes?: number
  native_group_chunks?: number
}

interface MyFootprintData {
  summary: MyFootprintSummary
  private_sessions: MyFootprintPrivateSession[]
  private_segments: MyFootprintPrivateSegment[]
  mentions: MyFootprintMentionItem[]
  mention_groups: MyFootprintMentionGroup[]
  diagnostics: MyFootprintDiagnostics
}

// 表情包缓存
const emojiCache: Map<string, string> = new Map()
const emojiDownloading: Map<string, Promise<string | null>> = new Map()
const FRIEND_EXCLUDE_USERNAMES = new Set(['medianote', 'floatbottle', 'qmessage', 'qqmail', 'fmessage'])

class ChatService {
  private configService: ConfigService
  private connected = false
  private readonly dbMonitorListeners = new Set<(type: string, json: string) => void>()
  private messageCursors: Map<string, { cursor: number; fetched: number; batchSize: number; startTime?: number; endTime?: number; ascending?: boolean; bufferedMessages?: any[] }> = new Map()
  private messageCursorMutex: boolean = false
  private readonly messageBatchDefault = 50
  private readonly messageCursorSessionLimit = 8
  private avatarCache: Map<string, ContactCacheEntry>
  private readonly avatarCacheTtlMs = 10 * 60 * 1000
  private readonly defaultV1AesKey = 'cfcd208495d565ef'
  private readonly contactCacheService: ContactCacheService
  private readonly messageCacheService: MessageCacheService
  private readonly sessionStatsCacheService: SessionStatsCacheService
  private readonly groupMyMessageCountCacheService: GroupMyMessageCountCacheService
  private readonly imageDecryptService: ImageDecryptService
  private voiceWavCache: LRUCache<string, Buffer>
  private voiceTranscriptCache: LRUCache<string, string>
  private voiceTranscriptPending = new Map<string, Promise<{ success: boolean; transcript?: string; error?: string }>>()
  private transcriptCacheLoaded = false
  private transcriptCacheDirty = false
  private transcriptFlushTimer: ReturnType<typeof setTimeout> | null = null
  private mediaDbsCache: string[] | null = null
  private mediaDbsCacheTime = 0
  private readonly mediaDbsCacheTtl = 300000 // 5分钟
  private readonly voiceWavCacheMaxEntries = 50
  // 缓存 media.db 的表结构信息
  private mediaDbSchemaCache = new Map<string, {
    voiceTable: string
    dataColumn: string
    chatNameIdColumn?: string
    timeColumn?: string
    name2IdTable?: string
  }>()
  // 缓存会话表信息，避免每次查询
  private sessionTablesCache = new Map<string, { tables: Array<{ tableName: string; dbPath: string }>; updatedAt: number }>()
  private messageTableColumnsCache = new Map<string, { columns: Set<string>; updatedAt: number }>()
  private messageName2IdTableCache = new Map<string, string | null>()
  private messageSenderIdCache = new Map<string, string | null>()
  private readonly sessionTablesCacheTtl = 300000 // 5分钟
  private readonly messageTableColumnsCacheTtlMs = 30 * 60 * 1000
  private messageDbCountSnapshotCache: {
    dbPaths: string[]
    dbSignature: string
    updatedAt: number
  } | null = null
  private readonly messageDbCountSnapshotCacheTtlMs = 8000
  private sessionMessageCountCache = new Map<string, { count: number; updatedAt: number }>()
  private sessionMessageCountHintCache = new Map<string, number>()
  private syntheticUnreadState = new Map<string, SyntheticUnreadState>()
  private sessionMessageCountBatchCache: {
    dbSignature: string
    sessionIdsKey: string
    counts: Record<string, number>
    updatedAt: number
  } | null = null
  private sessionMessageCountCacheScope = ''
  private readonly sessionMessageCountCacheTtlMs = 10 * 60 * 1000
  private readonly sessionMessageCountBatchCacheTtlMs = 5 * 60 * 1000
  private sessionDetailFastCache = new Map<string, { detail: SessionDetailFast; updatedAt: number }>()
  private sessionDetailExtraCache = new Map<string, { detail: SessionDetailExtra; updatedAt: number }>()
  private readonly sessionDetailFastCacheTtlMs = 60 * 1000
  private readonly sessionDetailExtraCacheTtlMs = 5 * 60 * 1000
  private sessionStatusCache = new Map<string, { isFolded?: boolean; isMuted?: boolean; updatedAt: number }>()
  private readonly sessionStatusCacheTtlMs = 10 * 60 * 1000
  private sessionStatsCacheScope = ''
  private sessionStatsMemoryCache = new Map<string, SessionStatsCacheEntry>()
  private sessionStatsPendingBasic = new Map<string, Promise<ExportSessionStats>>()
  private sessionStatsPendingFull = new Map<string, Promise<ExportSessionStats>>()
  private allGroupSessionIdsCache: { ids: string[]; updatedAt: number } | null = null
  private readonly sessionStatsCacheTtlMs = 10 * 60 * 1000
  private readonly allGroupSessionIdsCacheTtlMs = 5 * 60 * 1000
  private groupMyMessageCountCacheScope = ''
  private groupMyMessageCountMemoryCache = new Map<string, GroupMyMessageCountCacheEntry>()
  private initFailureDialogShown = false
  private readonly contactExtendedFieldCandidates = [
    'label_list', 'labelList', 'labels', 'label_names', 'labelNames', 'tags', 'tag_list', 'tagList',
    'detail_description', 'detailDescription', 'description', 'desc', 'contact_description', 'contactDescription', 'signature', 'sign',
    'country', 'province', 'city', 'region',
    'profile', 'introduction', 'phone', 'mobile', 'telephone', 'tel', 'vcard', 'card_info', 'cardInfo',
    'extra_buffer', 'extraBuffer'
  ]
  private readonly contactExtendedFieldCandidateSet = new Set(this.contactExtendedFieldCandidates.map((name) => name.toLowerCase()))
  private contactExtendedSelectableColumns: string[] | null = null
  private contactLabelNameMapCache: Map<number, string> | null = null
  private contactLabelNameMapCacheAt = 0
  private readonly visibilityAnomalyLogWindowMs = 30000
  private readonly visibilityAnomalyLogBurst = 3
  private visibilityAnomalyLogState = new Map<string, { windowStart: number; total: number; suppressed: number }>()
  private readonly contactLabelNameMapCacheTtlMs = 10 * 60 * 1000
  private contactsLoadInFlight: { mode: 'lite' | 'full'; promise: Promise<{ success: boolean; contacts?: ContactInfo[]; error?: string }> } | null = null
  private contactsMemoryCache = new Map<'lite' | 'full', { scope: string; updatedAt: number; contacts: ContactInfo[] }>()
  private readonly contactsMemoryCacheTtlMs = 3 * 60 * 1000
  private readonly contactDisplayNameCollator = new Intl.Collator('zh-CN')
  private readonly slowGetContactsLogThresholdMs = 1200

  constructor() {
    this.configService = new ConfigService()
    this.contactCacheService = new ContactCacheService(this.configService.getCacheBasePath())
    const persisted = this.contactCacheService.getAllEntries()
    this.avatarCache = new Map(Object.entries(persisted))
    this.messageCacheService = new MessageCacheService(this.configService.getCacheBasePath())
    this.sessionStatsCacheService = new SessionStatsCacheService(this.configService.getCacheBasePath())
    this.groupMyMessageCountCacheService = new GroupMyMessageCountCacheService(this.configService.getCacheBasePath())
    this.imageDecryptService = new ImageDecryptService()
    // 初始化LRU缓存，限制大小防止内存泄漏
    this.voiceWavCache = new LRUCache(this.voiceWavCacheMaxEntries)
    this.voiceTranscriptCache = new LRUCache(1000) // 最多缓存1000条转写记录
  }

  /**
   * 清理账号目录名
   */
  private cleanAccountDirName(dirName: string): string {
    const trimmed = dirName.trim()
    if (!trimmed) return trimmed

    if (trimmed.toLowerCase().startsWith('wxid_')) {
      const match = trimmed.match(/^(wxid_[^_]+)/i)
      if (match) return match[1]
      return trimmed
    }

    const suffixMatch = trimmed.match(/^(.+)_([a-zA-Z0-9]{4})$/)
    const cleaned = suffixMatch ? suffixMatch[1] : trimmed

    return cleaned
  }

  /**
   * 判断头像 URL 是否可用，过滤历史缓存里的错误 hex 数据。
   */
  private isValidAvatarUrl(avatarUrl?: string): avatarUrl is string {
    const normalized = String(avatarUrl || '').trim()
    if (!normalized) return false
    const normalizedLower = normalized.toLowerCase()
    if (normalizedLower.includes('base64,ffd8')) return false
    if (normalizedLower.startsWith('ffd8')) return false
    return true
  }

  private extractErrorCode(message?: string | null): number | null {
    const text = String(message || '').trim()
    if (!text) return null
    const match = text.match(/(?:错误码\s*[:：]\s*|\()(-?\d{2,6})(?:\)|\b)/)
    if (!match) return null
    const parsed = Number(match[1])
    return Number.isFinite(parsed) ? parsed : null
  }

  private toCodeOnlyMessage(rawMessage?: string | null, fallbackCode = -3999): string {
    const code = this.extractErrorCode(rawMessage) ?? fallbackCode
    return `错误码: ${code}`
  }

  private async maybeShowInitFailureDialog(errorMessage: string): Promise<void> {
    if (!app.isPackaged) return
    if (this.initFailureDialogShown) return

    const code = this.extractErrorCode(errorMessage)
    if (code === null) return
    const isSecurityCode =
      code === -101 ||
      code === -102 ||
      code === -2299 ||
      code === -2301 ||
      code === -2302 ||
      code === -1006 ||
      (code <= -2201 && code >= -2212)
    if (!isSecurityCode) return

    this.initFailureDialogShown = true
    const detail = [
      `错误码: ${code}`
    ].join('\n')

    try {
      await dialog.showMessageBox({
        type: 'error',
        title: 'WeFlow 启动失败',
        message: '启动失败，请反馈错误码。',
        detail,
        buttons: ['确定'],
        noLink: true
      })
    } catch {
      // 弹窗失败不阻断主流程
    }
  }

  /**
   * 连接数据库
   */
  async connect(): Promise<{ success: boolean; error?: string }> {
    try {
      if (this.connected && wcdbService.isReady()) {
        return { success: true }
      }
      const wxid = this.configService.get('myWxid')
      const dbPath = this.configService.get('dbPath')
      const decryptKey = this.configService.get('decryptKey')
      if (!wxid) {
        return { success: false, error: '请先在设置页面配置微信ID' }
      }
      if (!dbPath) {
        return { success: false, error: '请先在设置页面配置数据库路径' }
      }
      if (!decryptKey) {
        return { success: false, error: '请先在设置页面配置解密密钥' }
      }

      const cleanedWxid = this.cleanAccountDirName(wxid)
      const openOk = await wcdbService.open(dbPath, decryptKey, cleanedWxid)
      if (!openOk) {
        const detailedError = this.toCodeOnlyMessage(await wcdbService.getLastInitError())
        await this.maybeShowInitFailureDialog(detailedError)
        return { success: false, error: detailedError }
      }

      this.connected = true

      // 设置数据库监控
      this.setupDbMonitor()

      // 预热 listMediaDbs 缓存（后台异步执行，不阻塞连接）
      this.warmupMediaDbsCache()

      return { success: true }
    } catch (e) {
      console.error('ChatService: 连接数据库失败:', e)
      return { success: false, error: this.toCodeOnlyMessage(String(e), -3998) }
    }
  }

  private monitorSetup = false

  addDbMonitorListener(listener: (type: string, json: string) => void): () => void {
    this.dbMonitorListeners.add(listener)
    return () => {
      this.dbMonitorListeners.delete(listener)
    }
  }

  private setupDbMonitor() {
    if (this.monitorSetup) return
    this.monitorSetup = true

    // 使用 C++数据服务内部的文件监控 (ReadDirectoryChangesW)
    // 这种方式更高效，且不占用 JS 线程，并能直接监听 session/message 目录变更
    wcdbService.setMonitor((type, json) => {
      this.handleSessionStatsMonitorChange(type, json)
      for (const listener of this.dbMonitorListeners) {
        try {
          listener(type, json)
        } catch (error) {
          console.error('[ChatService] 数据库监听回调失败:', error)
        }
      }
      const windows = BrowserWindow.getAllWindows()
      // 广播给所有渲染进程窗口
      windows.forEach((win) => {
        if (!win.isDestroyed()) {
          win.webContents.send('wcdb-change', { type, json })
        }
      })
    })
  }

  /**
   * 预热 media 数据库列表缓存（后台异步执行）
   */
  private async warmupMediaDbsCache(): Promise<void> {
    try {
      const result = await wcdbService.listMediaDbs()
      if (result.success && result.data) {
        this.mediaDbsCache = result.data as string[]
        this.mediaDbsCacheTime = Date.now()
      }
    } catch (e) {
      // 静默失败，不影响主流程
    }
  }

  async warmupMessageDbSnapshot(): Promise<{ success: boolean; messageDbCount?: number; mediaDbCount?: number; error?: string }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) {
        return { success: false, error: connectResult.error || '数据库未连接' }
      }

      const [messageSnapshot, mediaResult] = await Promise.all([
        this.getMessageDbCountSnapshot(true),
        wcdbService.listMediaDbs()
      ])

      let messageDbCount = 0
      if (messageSnapshot.success && Array.isArray(messageSnapshot.dbPaths)) {
        messageDbCount = messageSnapshot.dbPaths.length
      }

      let mediaDbCount = 0
      if (mediaResult.success && Array.isArray(mediaResult.data)) {
        this.mediaDbsCache = [...mediaResult.data]
        this.mediaDbsCacheTime = Date.now()
        mediaDbCount = mediaResult.data.length
      }

      if (!messageSnapshot.success && !mediaResult.success) {
        return {
          success: false,
          error: messageSnapshot.error || mediaResult.error || '初始化消息库索引失败'
        }
      }

      return { success: true, messageDbCount, mediaDbCount }
    } catch (e) {
      return { success: false, error: String(e) }
    }
  }

  private async ensureConnected(): Promise<{ success: boolean; error?: string }> {
    if (this.connected && wcdbService.isReady()) {
      return { success: true }
    }
    if (!wcdbService.isReady()) {
      this.monitorSetup = false
    }
    const result = await this.connect()
    if (!result.success) {
      this.connected = false
      return { success: false, error: result.error }
    }
    return { success: true }
  }

  /**
   * 关闭数据库连接
   */
  private async closeMessageCursorBySession(sessionId: string): Promise<void> {
    const state = this.messageCursors.get(sessionId)
    if (!state) return
    try {
      await wcdbService.closeMessageCursor(state.cursor)
    } catch (error) {
      console.warn(`[ChatService] 关闭消息游标失败: ${sessionId}`, error)
    } finally {
      this.messageCursors.delete(sessionId)
    }
  }

  private async trimMessageCursorStates(activeSessionId: string): Promise<void> {
    if (this.messageCursors.size <= this.messageCursorSessionLimit) return
    for (const [sessionId] of this.messageCursors) {
      if (this.messageCursors.size <= this.messageCursorSessionLimit) break
      if (sessionId === activeSessionId) continue
      await this.closeMessageCursorBySession(sessionId)
    }
  }

  close(): void {
    try {
      for (const state of this.messageCursors.values()) {
        wcdbService.closeMessageCursor(state.cursor)
      }
      this.messageCursors.clear()
      wcdbService.close()
    } catch (e) {
      console.error('ChatService: 关闭数据库失败:', e)
    }
    this.connected = false
    this.monitorSetup = false
  }

  /**
   * 修改消息内容
   */
  async updateMessage(sessionId: string, localId: number, createTime: number, newContent: string): Promise<{ success: boolean; error?: string }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) return { success: false, error: connectResult.error }
      return await wcdbService.updateMessage(sessionId, localId, createTime, newContent)
    } catch (e) {
      return { success: false, error: String(e) }
    }
  }

  /**
   * 删除消息
   */
  async deleteMessage(sessionId: string, localId: number, createTime: number, dbPathHint?: string): Promise<{ success: boolean; error?: string }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) return { success: false, error: connectResult.error }
      return await wcdbService.deleteMessage(sessionId, localId, createTime, dbPathHint)
    } catch (e) {
      return { success: false, error: String(e) }
    }
  }

  async checkAntiRevokeTriggers(sessionIds: string[]): Promise<{
    success: boolean
    rows?: Array<{ sessionId: string; success: boolean; installed?: boolean; error?: string }>
    error?: string
  }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) return { success: false, error: connectResult.error }
      const { validIds, invalidRows } = await this.filterAntiRevokeSessionIds(sessionIds)
      const result = validIds.length > 0
        ? await wcdbService.checkMessageAntiRevokeTriggers(validIds)
        : { success: true, rows: [] }
      if (!result.success) return result
      return { success: true, rows: [...(result.rows || []), ...invalidRows] }
    } catch (e) {
      return { success: false, error: String(e) }
    }
  }

  async installAntiRevokeTriggers(sessionIds: string[]): Promise<{
    success: boolean
    rows?: Array<{ sessionId: string; success: boolean; alreadyInstalled?: boolean; error?: string }>
    error?: string
  }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) return { success: false, error: connectResult.error }
      const { validIds, invalidRows } = await this.filterAntiRevokeSessionIds(sessionIds)
      const result = validIds.length > 0
        ? await wcdbService.installMessageAntiRevokeTriggers(validIds)
        : { success: true, rows: [] }
      if (!result.success) return result
      return { success: true, rows: [...(result.rows || []), ...invalidRows] }
    } catch (e) {
      return { success: false, error: String(e) }
    }
  }

  async uninstallAntiRevokeTriggers(sessionIds: string[]): Promise<{
    success: boolean
    rows?: Array<{ sessionId: string; success: boolean; error?: string }>
    error?: string
  }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) return { success: false, error: connectResult.error }
      const { validIds, invalidRows } = await this.filterAntiRevokeSessionIds(sessionIds)
      const result = validIds.length > 0
        ? await wcdbService.uninstallMessageAntiRevokeTriggers(validIds)
        : { success: true, rows: [] }
      if (!result.success) return result
      return { success: true, rows: [...(result.rows || []), ...invalidRows] }
    } catch (e) {
      return { success: false, error: String(e) }
    }
  }

  /**
   * 获取会话列表（优化：先返回基础数据，不等待联系人信息加载）
   */
  async getSessions(): Promise<{ success: boolean; sessions?: ChatSession[]; error?: string }> {
    try {
      const connectResult = await this.ensureConnected()
      if (!connectResult.success) {
        return { success: false, error: connectResult.error }
      }
      this.refreshSessionMessageCountCacheScope()

      const result = await wcdbService.getSessions()
      if (!result.success || !result.sessions) {
        return { success: false, error: result.error || '获取会话失败' }
      }
      const rows = result.sessions as Record<string, any>[]
      if (rows.length > 0 && (rows[0]._error || rows[0]._info)) {
        const info = rows[0]
        const detail = info._error || info._info
        const tableInfo = info.table ? ` table=${info.table}` : ''
        const tables = info.tables ? ` tables=${info.tables}` : ''
        const columns = info.columns ? ` columns=${info.columns}` : ''
        return { success: false, error: `会话表异常: ${detail}${tableInfo}${tables}${columns}` }
      }

      const openimLocalTypeMap = await this.loadContactLocalTypeMapForEnterpriseOpenim(rows.map((row) =>
        String(
          row.username ||
          row.user_name ||
          row.userName ||
          row.usrName ||
          row.UsrName ||
          row.talker ||
          row.talker_id ||
          row.talkerId ||
          ''
        ).trim()
      ))

      // 转换为 ChatSession（先加载缓存，但不等待额外状态查询）
      const sessions: ChatSession[] = []
      const now = Date.now()
      const myWxid = this.configService.get('myWxid')

      for (const row of rows) {
        const username =
          row.username ||
          row.user_name ||
          row.userName ||
          row.usrName ||
          row.UsrName ||
          row.talker ||
          row.talker_id ||
          row.talkerId ||
          ''

        let sessionLocalType = this.getSessionLocalType(row)
        if (!Number.isFinite(sessionLocalType) && this.isEnterpriseOpenimUsername(username)) {
          sessionLocalType = openimLocalTypeMap.get(username)
        }
        if (!this.shouldKeepSession(username, sessionLocalType)) continue

        const sortTs = parseInt(
          row.sort_timestamp ||
          row.sortTimestamp ||
          row.sort_time ||
          row.sortTime ||
          '0',
          10
        )
        const lastTs = parseInt(
          row.last_timestamp ||
          row.lastTimestamp ||
          row.last_msg_time ||
          row.lastMsgTime ||
          String(sortTs),
          10
        )

        const summary = this.cleanString(row.summary || row.digest || row.last_msg || row.lastMsg || '')
        const lastMsgType = parseInt(row.last_msg_type || row.lastMsgType || '0', 10)
        const messageCountHintRaw =
          row.message_count ??
          row.messageCount ??
          row.msg_count ??
          row.msgCount ??
          row.total_count ??
          row.totalCount ??
          row.n_msg ??
          row.nMsg ??
          row.message_num ??
          row.messageNum
        const parsedMessageCountHint = Number(messageCountHintRaw)
        const messageCountHint = Number.isFinite(parsedMessageCountHint) && parsedMessageCountHint >= 0
          ? Math.floor(parsedMessageCountHint)
          : undefined

        // 先尝试从缓存获取联系人信息（快速路径）
        let displayName = username
        let avatarUrl: string | undefined = undefined
        const cached = this.avatarCache.get(username)
        if (cached) {
          displayName = cached.displayName || username
          avatarUrl = cached.avatarUrl
        }

        const nextSession: ChatSession = {
          username,
          type: parseInt(row.type || '0', 10),
          unreadCount: parseInt(row.unread_count || row.unreadCount || row.unreadcount || '0', 10),
          summary: summary || this.getMessageTypeLabel(lastMsgType),
          sortTimestamp: sortTs,
          lastTimestamp: lastTs,
          lastMsgType,
          messageCountHint,
          displayName,
          avatarUrl,
          lastMsgSender: row.last_msg_sender,
          lastSenderDisplayName: row.last_sender_display_name,
          selfWxid: myWxid
        }

        const cachedStatus = this.sessionStatusCache.get(username)
        if (cachedStatus && now - cachedStatus.updatedAt <= this.sessionStatusCacheTtlMs) {
          nextSession.isFolded = cachedStatus.isFolded
          nextSession.isMuted = cachedStatus.isMuted
        }

        sessions.push(nextSession)

        if (typeof messageCountHint === 'number') {
          this.sessionMessageCountHintCache.set(username, messageCountHint)
          this.sessionMessageCountCache.set(username, {
            count: messageCountHint,
            updatedAt: Date.now()
          })
        }
      }

      await this.addMissingOfficialSessions(sessions, myWxid)
      await this.applySyntheticUnreadCounts(sessions)
      sessions.sort((a, b) => Number(b.sortTimestamp || b.lastTimestamp || 0) - Number(a.sortTimestamp || a.lastTimestamp || 0))

      // 不等待联系人信息加载，直接返回基础会话列表
      // 前端可以异步调用 enrichSessionsWithContacts 来补充信息
      return { success: true, sessions }
    } catch (e) {
      console.error('ChatService: 获取会话列表失败:', e)
      return { success: false, error: String(e) }
    }
  }

  async getAntiRevokeSessions(): Promise<{ success: boolean; sessions?: ChatSession[]; error?: string }> {
    try {
      const result = await this.getSessions()
      if (!result.success || !Array.isArray(result.sessions)) {
        return { success: false, error: result.error || '获取会话失败' }
      }

      return {
        success: true,
        sessions: result.sessions.filter((session) => !String(session.username || '').startsWith('gh_'))
      }
    } catch (e) {
      console.error('ChatService: 获取防撤回会话列表失败:', e)
      return { success: false, error: String(e) }
    }
  }

  private getSessionUsername(row: Record<string, any>): string {
    return String(
      row.username ||
      row.user_name ||
      row.userName ||
      row.usrName ||
      row.UsrName ||
      row.talker ||
      row.talker_id ||
      row.talkerId ||
      ''
    ).trim()
  }

  private isAntiRevokeContactRow(username: string, row: Record<string, any>): boolean {
    if (!username) return false
    if (username.endsWith('@chatroom')) return true
    if (username.startsWith('gh_')) return false

    const localType = this.getRowInt(row, ['local_type', 'localType', 'WCDB_CT_local_type'], Number.NaN)
    const lowered = username.toLowerCase()
    if (this.isEnterpriseOpenimUsername(username)) {
      return this.isAllowedEnterpriseOpenimByLocalType(username, localType)
    }
    if (lowered.startsWith('weixin') && lowered !== 'weixin') return true
    return localType === 1 && !FRIEND_EXCLUDE_USERNAMES.has(username)
  }

  private async loadAntiRevokeContactMap(usernames: string[]): Promise<Map<string, { displayName?: string }>> {
    const targets = Array.from(new Set((usernames || []).map((value) => String(value || '').trim()).filter(Boolean)))
    const map = new Map<string, { displayName?: string }>()
    if (targets.length === 0) return map

    try {
      const contactResult = await wcdbService.getContactsCompact(targets)
      if (!contactResult.success || !Array.isArray(contactResult.contacts)) return map

      for (const row of contactResult.contacts as Record<string, any>[]) {
        const username = String(row.username || '').trim()
        if (!username || !this.isAntiRevokeContactRow(username, row)) continue
        map.set(username, {
          displayName: String(row.remark || row.nick_name || row.nickName || row.alias || username).trim()
        })
      }
    } catch {
      return map
    }

    return map
  }

  private async hasAntiRevokeMessageTables(sessionId: string): Promise<boolean> {
    try {
      const tableStatsResult = await wcdbService.getMessageTableStats(sessionId)
      if (!tableStatsResult.success || !Array.isArray(tableStatsResult.tables)) return false
      return tableStatsResult.tables.some((row: Record<string, any>) => {
        const tableName = String(row.table_name || row.tableName || '').trim()
        return tableName.length > 0
      })
    } catch {
      return false
    }
  }

  private async buildAntiRevokeSessionsFromRows(rows: Record<string, any>[]): Promise<ChatSession[]> {
    if (rows.length > 0 && (rows[0]._error || rows[0]._info)) return []

    const candidateRows: Array<{ username: string; row: Record<string, any> }> = []
    const privateCandidateIds: string[] = []
    const openimLocalTypeMap = await this.loadContactLocalTypeMapForEnterpriseOpenim(rows.map((row) => this.getSessionUsername(row)))

    for (const row of rows) {
      const username = this.getSessionUsername(row)
      if (!username) continue

      let sessionLocalType = this.getSessionLocalType(row)
      if (!Number.isFinite(sessionLocalType) && this.isEnterpriseOpenimUsername(username)) {
        sessionLocalType = openimLocalTypeMap.get(username)
      }
      if (!this.shouldKeepSession(username, sessionLocalType)) continue

      if (username.endsWith('@chatroom')) {
        candidateRows.push({ username, row })
      } else {
        privateCandidateIds.push(username)
        candidateRows.push({ username, row })
      }
    }

    const contactMap = await this.loadAntiRevokeContactMap(privateCandidateIds)
    const sessions: ChatSession[] = []
    const myWxid = this.configService.get('myWxid')
    const now = Date.now()

    for (const { username, row } of candidateRows) {
      const isGroup = username.endsWith('@chatroom')
      if (!isGroup && !contactMap.has(username)) continue
      if (!await this.hasAntiRevokeMessageTables(username)) continue

      const sortTs = parseInt(
        row.sort_timestamp ||
        row.sortTimestamp ||
        row.sort_time ||
        row.sortTime ||
        '0',
        10
      )
      const lastTs = parseInt(
        row.last_timestamp ||
        row.lastTimestamp ||
        row.last_msg_time ||
        row.lastMsgTime ||
        String(sortTs),
        10
      )
      const summary = this.cleanString(row.summary || row.digest || row.last_msg || row.lastMsg || '')
      const lastMsgType = parseInt(row.last_msg_type || row.lastMsgType || '0', 10)
      const cached = this.avatarCache.get(username)
      const contact = contactMap.get(username)

      const session: ChatSession = {
        username,
        type: parseInt(row.type || '0', 10),
        unreadCount: parseInt(row.unread_count || row.unreadCount || row.unreadcount || '0', 10),
        summary: summary || this.getMessageTypeLabel(lastMsgType),
        sortTimestamp: sortTs,
        lastTimestamp: lastTs,
        lastMsgType,
        displayName: contact?.displayName || cached?.displayName || username,
        avatarUrl: cached?.avatarUrl,
        lastMsgSender: row.last_msg_sender,
        lastSenderDisplayName: row.last_sender_display_name,
        selfWxid: myWxid
      }

      const cachedStatus = this.sessionStatusCache.get(username)
      if (cachedStatus && now - cachedStatus.updatedAt <= this.sessionStatusCacheTtlMs) {
        session.isFolded = cachedStatus.isFolded
        session.isMuted = cachedStatus.isMuted
      }

      sessions.push(session)
    }

    return sessions
  }

  private async filterAntiRevokeSessionIds(sessionIds: string[]): Promise<{
    validIds: string[]
    invalidRows: Array<{ sessionId: string; success: false; error: string }>
  }> {
    const normalizedIds = Array.from(new Set((sessionIds || []).map((id) => String(id || '').trim()).filter(Boolean)))
    if (normalizedIds.length === 0) return { validIds: [], invalidRows: [] }

    const sessionsResult = await this.getAntiRevokeSessions()
    const allowedIds = new Set((sessionsResult.sessions || []).map((session) => session.username))
    const validIds = normalizedIds.filter((sessionId) => allowedIds.has(sessionId))
    const invalidRows = normalizedIds
      .filter((sessionId) => !allowedIds.has(sessionId))
      .map((sessionId) => ({
        sessionId,
        success: false as const,
        error: '该会话不是联系人或群聊，或不存在可安装防撤回的消息表'
      }))

    return { validIds, invalidRows }
  }

  private async addMissingOfficialSessions(sessions: ChatSession[], myWxid?: string): Promise<void> {
    const existing = new Set(sessions.map((session) => String(session.username || '').trim()).filter(Boolean))
    try {
      const contactResult = await wcdbService.getContactsCompact()
      if (!contactResult.success || !Array.isArray(contactResult.contacts)) return

      for (const row of contactResult.contacts as Record<string, any>[]) {
        const username = String(row.username || '').trim()
        if (!username || existing.has(username)) continue
        const lowered = username.toLowerCase()
        const localType = this.getRowInt(row, ['local_type', 'localType', 'WCDB_CT_local_type'], Number.NaN)
        const isOfficial = username.startsWith('gh_')
        const isSpecialWeixin = lowered.startsWith('weixin') && lowered !== 'weixin'
        const isSpecialOpenim = this.isAllowedEnterpriseOpenimByLocalType(username, localType)
        if (!isOfficial && !isSpecialWeixin && !isSpecialOpenim) continue

        sessions.push({
          username,
          type: 0,
          unreadCount: 0,
          summary: isOfficial ? '查看公众号历史消息' : '暂无会话记录',
          sortTimestamp: 0,
          lastTimestamp: 0,
          lastMsgType: 0,
          displayName: row.remark || row.nick_name || row.alias || username,
          avatarUrl: undefined,
          selfWxid: myWxid
        })
        existing.add(username)
      }
    } catch (error) {
      console.warn('[ChatService] 补充公众号会话失败:', error)
    }
  }

  private shouldUseSyntheticUnread(sessionId: string): boolean {
    const normalized = String(sessionId || '').trim()
    return normalized.startsWith('gh_')
  }

  private async getSessionMessageStatsSnapshot(sessionId: string): Promise<{ total: number; latestTimestamp: number }> {
    const tableStatsResult = await wcdbService.getMessageTableStats(sessionId)
    if (!tableStatsResult.success || !Array.isArray(tableStatsResult.tables)) {
      return { total: 0, latestTimestamp: 0 }
    }

    let total = 0
    let latestTimestamp = 0
    for (const row of tableStatsResult.tables as Record<string, any>[]) {
      const count = Number(row.count ?? row.message_count ?? row.messageCount ?? 0)
      if (Number.isFinite(count) && count > 0) {
        total += Math.floor(count)
      }

      const latest = Number(
        row.last_timestamp ??
        row.lastTimestamp ??
        row.last_time ??
        row.lastTime ??
        row.max_create_time ??
        row.maxCreateTime ??
        0
      )
      if (Number.isFinite(latest) && latest > latestTimestamp) {
        latestTimestamp = Math.floor(latest)
      }
    }

    return { total, latestTimestamp }
  }

  private async applySyntheticUnreadCounts(sessions: ChatSession[]): Promise<void> {
    const candidates = sessions.filter((session) => this.shouldUseSyntheticUnread(session.username))
    if (candidates.length === 0) return

    for (const session of candidates) {
      try {
        const snapshot = await this.getSessionMessageStatsSnapshot(session.username)
        const latestTimestamp = Math.max(
          Number(session.lastTimestamp || 0),
          Number(session.sortTimestamp || 0),
          snapshot.latestTimestamp
        )
        if (latestTimestamp > 0) {
          session.lastTimestamp = latestTimestamp
          session.sortTimestamp = Math.max(Number(session.sortTimestamp || 0), latestTimestamp)
        }
        if (snapshot.total > 0) {
          session.messageCountHint = Math.max(Number(session.messageCountHint || 0), snapshot.total)
          this.sessionMessageCountHintCache.set(session.username, session.messageCountHint)
        }

        let state = this.syntheticUnreadState.get(session.username)
        if (!state) {
          const initialUnread = await this.getInitialSyntheticUnreadState(session.username, latestTimestamp)
          state = {
            readTimestamp: latestTimestamp,
            scannedTimestamp: latestTimestamp,
            latestTimestamp,
            unreadCount: initialUnread.count
          }
          if (initialUnread.latestMessage) {
            state.summary = this.getSessionSummaryFromMessage(initialUnread.latestMessage)
            state.summaryTimestamp = Number(initialUnread.latestMessage.createTime || latestTimestamp)
            state.lastMsgType = Number(initialUnread.latestMessage.localType || 0)
          }
          this.syntheticUnreadState.set(session.username, state)
        }

        let latestMessageForSummary: Message | undefined
        if (latestTimestamp > state.scannedTimestamp) {
          const newMessagesResult = await this.getNewMessages(
            session.username,
            Math.max(0, state.scannedTimestamp),
            1000
          )
          if (newMessagesResult.success && Array.isArray(newMessagesResult.messages)) {
            let nextUnread = state.unreadCount
            let nextScannedTimestamp = state.scannedTimestamp
            for (const message of newMessagesResult.messages) {
              const createTime = Number(message.createTime || 0)
              if (!Number.isFinite(createTime) || createTime <= state.scannedTimestamp) continue
              if (message.isSend === 1) continue
              nextUnread += 1
              latestMessageForSummary = message
              if (createTime > nextScannedTimestamp) {
                nextScan