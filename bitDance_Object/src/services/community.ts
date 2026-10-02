import { getToken } from './auth'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function headersWithAuth(): HeadersInit {
  const t = getToken()
  return {
    ...JSON_HEADERS,
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
  }
}

async function ensureOk(response: Response, fallback: string) {
  if (response.ok) return
  const raw = await response.text().catch(() => '')
  let parsed: { message?: string; fields?: Record<string, string> } | null = null
  if (raw) {
    try {
      parsed = JSON.parse(raw) as { message?: string; fields?: Record<string, string> }
    } catch {
      parsed = null
    }
  }
  let msg = parsed?.message || fallback
  if (parsed?.fields && typeof parsed.fields === 'object') {
    const detail = Object.entries(parsed.fields)
      .map(([k, v]) => `${k}: ${v}`)
      .join('；')
    if (detail) {
      msg = `${msg}（${detail}）`
    }
  }
  if (msg === fallback && raw && !parsed) {
    msg = raw.length > 400 ? `${raw.slice(0, 400)}…` : raw
  }
  throw new Error(msg)
}

export interface PostSummaryDTO {
  id: number
  title: string
  excerpt: string
  authorUsername: string
  likeCount: number
  commentCount: number
  createdAt: string
}

export interface PostDetailDTO {
  id: number
  title: string
  content: string
  authorUsername: string
  likeCount: number
  commentCount: number
  createdAt: string
  likedByMe: boolean
}

export interface PostPageDTO {
  items: PostSummaryDTO[]
  total: number
  page: number
  size: number
}

export interface CommentDTO {
  id: number
  body: string
  authorUsername: string
  likeCount: number
  createdAt: string
  likedByMe: boolean
}

export interface LikeResponseDTO {
  liked: boolean
  likeCount: number
}

export async function fetchTrending(limit = 10): Promise<PostSummaryDTO[]> {
  const q = new URLSearchParams({ limit: String(limit) })
  const res = await fetch(`/api/community/trending?${q}`)
  await ensureOk(res, '加载热门失败')
  return res.json() as Promise<PostSummaryDTO[]>
}

export async function fetchPosts(params: {
  q?: string
  page?: number
  size?: number
}): Promise<PostPageDTO> {
  const q = new URLSearchParams()
  if (params.q?.trim()) q.set('q', params.q.trim())
  if (params.page != null) q.set('page', String(params.page))
  if (params.size != null) q.set('size', String(params.size))
  const res = await fetch(`/api/community/posts?${q}`)
  await ensureOk(res, '加载帖子列表失败')
  return res.json() as Promise<PostPageDTO>
}

export async function fetchPost(id: number): Promise<PostDetailDTO> {
  const res = await fetch(`/api/community/posts/${id}`, {
    headers: headersWithAuth(),
  })
  await ensureOk(res, '加载帖子失败')
  return res.json() as Promise<PostDetailDTO>
}

export async function createPost(title: string, content: string): Promise<PostDetailDTO> {
  const res = await fetch('/api/community/posts', {
    method: 'POST',
    headers: headersWithAuth(),
    body: JSON.stringify({ title, content }),
  })
  await ensureOk(res, '发帖失败')
  return res.json() as Promise<PostDetailDTO>
}

export async function togglePostLike(postId: number): Promise<LikeResponseDTO> {
  const res = await fetch(`/api/community/posts/${postId}/like`, {
    method: 'POST',
    headers: headersWithAuth(),
  })
  await ensureOk(res, '点赞失败')
  return res.json() as Promise<LikeResponseDTO>
}

export async function fetchComments(postId: number, sort: 'new' | 'likes'): Promise<CommentDTO[]> {
  const q = new URLSearchParams({ sort })
  const res = await fetch(`/api/community/posts/${postId}/comments?${q}`, {
    headers: headersWithAuth(),
  })
  await ensureOk(res, '加载评论失败')
  return res.json() as Promise<CommentDTO[]>
}

export async function createComment(postId: number, body: string): Promise<CommentDTO> {
  const res = await fetch(`/api/community/posts/${postId}/comments`, {
    method: 'POST',
    headers: headersWithAuth(),
    body: JSON.stringify({ body }),
  })
  await ensureOk(res, '发表评论失败')
  return res.json() as Promise<CommentDTO>
}

export async function toggleCommentLike(commentId: number): Promise<LikeResponseDTO> {
  const res = await fetch(`/api/community/comments/${commentId}/like`, {
    method: 'POST',
    headers: headersWithAuth(),
  })
  await ensureOk(res, '点赞失败')
  return res.json() as Promise<LikeResponseDTO>
}
