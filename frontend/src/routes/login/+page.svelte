<script lang="ts">
	import { api } from '$lib/api';
	import { loadUser } from '$lib/stores/auth';
	import { goto } from '$app/navigation';

	let mode = $state<'login' | 'register'>('login');
	let email = $state('');
	let password = $state('');
	let displayName = $state('');
	let error = $state('');
	let loading = $state(false);

	async function submit() {
		loading = true;
		error = '';
		try {
			let result;
			if (mode === 'register') {
				result = await api.register(email, displayName, password);
			} else {
				result = await api.login(email, password);
			}
			sessionStorage.setItem('token', result.access_token);
			await loadUser();
			goto('/');
		} catch (e: any) {
			error = e.message;
		} finally {
			loading = false;
		}
	}
</script>

<div class="auth-page">
	<div class="auth-card glass">
		<h1 class="serif">{mode === 'login' ? 'Welcome back' : 'Create account'}</h1>
		<p class="subtitle">{mode === 'login' ? 'Log in to find your matches.' : 'Sign up to start matching.'}</p>

		<form onsubmit={(e) => { e.preventDefault(); submit(); }}>
			{#if mode === 'register'}
				<div class="field">
					<label for="name">Name</label>
					<input id="name" type="text" bind:value={displayName} placeholder="Your display name" required />
				</div>
			{/if}
			<div class="field">
				<label for="email">Email</label>
				<input id="email" type="email" bind:value={email} placeholder="you@example.com" required />
			</div>
			<div class="field">
				<label for="password">Password</label>
				<input id="password" type="password" bind:value={password} placeholder="Enter password" required />
			</div>
			{#if error}<p class="error">{error}</p>{/if}
			<button class="btn-primary submit-btn" type="submit" disabled={loading}>
				{loading ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Create account'}
			</button>
		</form>

		<div class="divider"></div>

		<p class="switch">
			{#if mode === 'login'}
				New here? <button class="link-btn" onclick={() => mode = 'register'}>Create an account</button>
			{:else}
				Have an account? <button class="link-btn" onclick={() => mode = 'login'}>Log in</button>
			{/if}
		</p>
	</div>
</div>

<style>
	.auth-page {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: calc(100vh - 160px);
	}
	.auth-card {
		width: 100%;
		max-width: 400px;
		padding: 40px;
		box-shadow: var(--glow);
	}
	h1 {
		font-size: 30px;
		font-weight: 700;
		font-style: italic;
		color: var(--gold-light);
	}
	.subtitle {
		color: var(--text-secondary);
		margin-top: 6px;
		margin-bottom: 32px;
		font-size: 14px;
	}
	form {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	label {
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.error {
		color: var(--red);
		font-size: 13px;
		padding: 10px 14px;
		background: var(--red-light);
		border-radius: var(--radius-sm);
		border: 1px solid rgba(248, 113, 113, 0.2);
	}
	.submit-btn {
		margin-top: 8px;
		padding: 13px;
		font-size: 15px;
		font-weight: 600;
		border-radius: 9999px;
	}
	.divider {
		height: 1px;
		background: var(--glass-border);
		margin: 28px 0;
	}
	.switch {
		text-align: center;
		font-size: 14px;
		color: var(--text-secondary);
	}
	.link-btn {
		background: none;
		color: var(--gold-light);
		padding: 0;
		font-size: 14px;
		font-weight: 500;
		border: none;
		cursor: pointer;
	}
	.link-btn:hover {
		color: var(--gold-hover);
		text-decoration: underline;
	}
</style>
