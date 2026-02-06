use tauri::WebviewUrl;

/// Generate server connection arguments (host, port, token).
///
/// - Debug: reads from env vars with defaults (no token by default).
/// - Release: auto-generates a secure random token.
pub fn generate_server_args() -> (String, String, String) {
    #[cfg(debug_assertions)]
    {
        let host = std::env::var("SYFT_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
        let port = std::env::var("SYFT_PORT").unwrap_or_else(|_| "8080".to_string());
        let token = std::env::var("SYFT_ADMIN_API_KEY").unwrap_or_default();
        (host, port, token)
    }
    #[cfg(not(debug_assertions))]
    {
        let host = "127.0.0.1".to_string();
        let port = _get_random_available_port().to_string();
        let token = generate_secure_token();
        (host, port, token)
    }
}

/// Bind to port 0 to let the OS assign a random available port.
#[cfg(not(debug_assertions))]
fn _get_random_available_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .expect("Failed to find an available port")
        .local_addr()
        .expect("Failed to get local address")
        .port()
}

#[cfg(not(debug_assertions))]
fn generate_secure_token() -> String {
    use rand::rngs::OsRng;
    use rand::TryRngCore;
    let mut key = [0u8; 16];
    OsRng
        .try_fill_bytes(&mut key)
        .expect("Failed to generate secure token");
    hex::encode(key)
}

/// Build the frontend URL with connection params as hash query parameters.
/// Produces a URL like `#/?host=127.0.0.1&port=8080&authToken=abc123`
/// which Vue Router's hash history will parse as route `/` with query params.
pub fn generate_main_url(host: &str, port: &str, token: &str) -> WebviewUrl {
    let url = format!("#/?host={}&port={}&authToken={}", host, port, token);
    WebviewUrl::App(url.into())
}
