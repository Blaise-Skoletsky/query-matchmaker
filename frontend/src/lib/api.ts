const BASE = 'http://127.0.0.1:8000';

function getToken(): string | null {
	if (typeof window === 'undefined') return null;
	return sessionStorage.getItem('token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
	const token = getToken();
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(options.headers as Record<string, string> || {})
	};
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}

	const res = await fetch(`${BASE}${path}`, { ...options, headers });
	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw new Error(body.detail || `HTTP ${res.status}`);
	}
	if (res.status === 204) return undefined as T;
	return res.json();
}

export const api = {
	register(email: string, display_name: string, password: string) {
		return request<{ access_token: string }>('/api/auth/register', {
			method: 'POST',
			body: JSON.stringify({ email, display_name, password })
		});
	},
	login(email: string, password: string) {
		return request<{ access_token: string }>('/api/auth/login', {
			method: 'POST',
			body: JSON.stringify({ email, password })
		});
	},
	me() {
		return request<{ id: string; email: string; display_name: string }>('/api/auth/me');
	},
	converse(history: { role: string; content: string }[], context?: { location?: string; budget?: string; condition?: string; urgency?: string }) {
		return request<{ action: string; message: string | null; query_id: string | null }>('/api/conversation', {
			method: 'POST',
			body: JSON.stringify({ history, ...context })
		});
	},
	listQueries() {
		return request<any[]>('/api/queries');
	},
	deleteQuery(id: string) {
		return request<void>(`/api/queries/${id}`, { method: 'DELETE' });
	},
	getMatchTrace(queryId: string) {
		return request<{ ready: boolean; trace: any }>(`/api/queries/${queryId}/trace`);
	},
	listMatches() {
		return request<any[]>('/api/matches');
	},
	acceptMatch(id: string) {
		return request<any>(`/api/matches/${id}/accept`, { method: 'POST' });
	},
	rejectMatch(id: string) {
		return request<any>(`/api/matches/${id}/reject`, { method: 'POST' });
	},
	listChatrooms() {
		return request<any[]>('/api/chatrooms');
	},
	getChatroom(id: string) {
		return request<{ id: string; name: string; created_at: string; members: { user_id: string; display_name: string }[] }>(`/api/chatrooms/${id}`);
	},
	getMessages(chatroomId: string) {
		return request<any[]>(`/api/chatrooms/${chatroomId}/messages`);
	},

	// Notifications
	listNotifications(unreadOnly = false) {
		const params = unreadOnly ? '?unread_only=true' : '';
		return request<any[]>(`/api/notifications${params}`);
	},
	notificationCount() {
		return request<{ unread: number; total: number }>('/api/notifications/count');
	},
	markNotificationRead(id: string) {
		return request<any>(`/api/notifications/${id}/read`, { method: 'POST' });
	},
	markAllNotificationsRead() {
		return request<void>('/api/notifications/read-all', { method: 'POST' });
	},

	// Recommendations
	getSimilarQueries(limit = 5) {
		return request<any[]>(`/api/recommendations/similar?limit=${limit}`);
	},
	getTrending(limit = 10) {
		return request<any[]>(`/api/recommendations/trending?limit=${limit}`);
	},
	getDemandGaps(limit = 5) {
		return request<any[]>(`/api/recommendations/demand-gaps?limit=${limit}`);
	},

	// Analytics
	getAnalyticsLatest() {
		return request<any>('/api/analytics/latest');
	},
	getAnalyticsSnapshots(limit = 30) {
		return request<any[]>(`/api/analytics/snapshots?limit=${limit}`);
	},

	// Agent status
	getAgentStatus() {
		return request<{ agents: any[] }>('/api/agents/status');
	}
};
