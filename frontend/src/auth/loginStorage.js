const AUTO_LOGIN_KEY = 'uang_pengiriman_auto_login';
const USERNAME_KEY = 'uang_pengiriman_username';

export function loadLoginPrefs() {
  return {
    autoLogin: localStorage.getItem(AUTO_LOGIN_KEY) === 'true',
    username: localStorage.getItem(USERNAME_KEY) || '',
  };
}

export function saveLoginPrefs(autoLogin, username) {
  localStorage.setItem(AUTO_LOGIN_KEY, autoLogin ? 'true' : 'false');
  if (autoLogin && username) {
    localStorage.setItem(USERNAME_KEY, username.trim());
  } else {
    localStorage.removeItem(USERNAME_KEY);
  }
}

export function clearLoginPrefs() {
  localStorage.removeItem(AUTO_LOGIN_KEY);
  localStorage.removeItem(USERNAME_KEY);
}
