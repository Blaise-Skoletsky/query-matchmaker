import { writable } from 'svelte/store';
import { api } from '$lib/api';

export const user = writable<{ id: string; email: string; display_name: string } | null>(null);
export const isLoggedIn = writable(false);
export const authLoaded = writable(false);

export async function loadUser() {
	const token = sessionStorage.getItem('token');
	if (!token) {
		authLoaded.set(true);
		return;
	}
	try {
		const me = await api.me();
		user.set(me);
		isLoggedIn.set(true);
	} catch {
		sessionStorage.removeItem('token');
		isLoggedIn.set(false);
	} finally {
		authLoaded.set(true);
	}
}

export function logout() {
	sessionStorage.removeItem('token');
	user.set(null);
	isLoggedIn.set(false);
}
