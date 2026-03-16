import SwiftUI
import WebKit

/// Vimeo プレイヤー: WKWebView + Vimeo Player SDK (postMessage API) で再生・タイムコード取得
struct VimeoPlayerView: UIViewRepresentable {
    /// 表示するVimeo動画ID
    let videoId: String
    /// 限定公開動画のプライバシーハッシュ（unlisted動画に必要）
    var privacyHash: String? = nil
    /// 現在の再生位置（秒）をバインド
    @Binding var currentTime: TimeInterval
    /// 再生中フラグ
    @Binding var isPlaying: Bool

    func makeCoordinator() -> Coordinator {
        Coordinator(currentTime: $currentTime, isPlaying: $isPlaying)
    }

    func makeUIView(context: Context) -> WKWebView {
        // JavaScriptメッセージハンドラを登録
        let contentController = WKUserContentController()
        contentController.add(context.coordinator, name: "vimeoTime")
        contentController.add(context.coordinator, name: "vimeoState")

        let config = WKWebViewConfiguration()
        config.userContentController = contentController
        // Vimeo Player.jsのpostMessageを受け取るためにインライン再生を許可
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.scrollView.isScrollEnabled = false
        webView.backgroundColor = .black
        webView.isOpaque = false

        // Vimeo iframe Player HTML を読み込む
        let html = buildPlayerHTML(videoId: videoId)
        // baseURLは外部ドメインを使用（vimeo.comやnilだとiframe/JS読み込みがブロックされる）
        webView.loadHTMLString(html, baseURL: URL(string: "https://video-director.app/"))

        context.coordinator.webView = webView
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        // isPlaying の変化に応じて play/pause を JavaScript 経由で制御
        // （タイムラインマーカータップ時のseekToも同じ経路で実行）
    }

    // MARK: - Vimeo Player HTML 生成

    private func buildPlayerHTML(videoId: String) -> String {
        // 限定公開動画はハッシュ付きembed URLが必要
        let hashParam = privacyHash.map { "?h=\($0)" } ?? ""
        let embedUrl = "https://player.vimeo.com/video/\(videoId)\(hashParam)"
        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          html, body { width: 100%; height: 100%; background: #000; overflow: hidden; }
          #player-container { width: 100%; height: 100%; }
          #player-container > div { width: 100% !important; height: 100% !important; }
          iframe { width: 100%; height: 100%; border: none; display: block; }
        </style>
        </head>
        <body>
        <div id="player-container">
          <div id="player"></div>
        </div>
        <script src="https://player.vimeo.com/api/player.js"></script>
        <script>
          var player = new Vimeo.Player('player', {
            url: '\(embedUrl)',
            width: '100%',
            responsive: true,
            title: false,
            byline: false,
            portrait: false,
            color: '1694F5'
          });

          // タイムコード更新を Swift へ送信（約1秒間隔）
          player.on('timeupdate', function(data) {
            window.webkit.messageHandlers.vimeoTime.postMessage({
              seconds: data.seconds,
              duration: data.duration,
              percent: data.percent
            });
          });

          // 再生状態の変化を Swift へ通知
          player.on('play', function() {
            window.webkit.messageHandlers.vimeoState.postMessage({ state: 'playing' });
          });
          player.on('pause', function() {
            window.webkit.messageHandlers.vimeoState.postMessage({ state: 'paused' });
          });
          player.on('ended', function() {
            window.webkit.messageHandlers.vimeoState.postMessage({ state: 'ended' });
          });

          // Swift 側からのコマンドを受け取る関数を公開
          function seekTo(seconds) {
            player.setCurrentTime(seconds);
          }
          function playVideo() {
            player.play();
          }
          function pauseVideo() {
            player.pause();
          }
        </script>
        </body>
        </html>
        """
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, WKScriptMessageHandler {
        @Binding var currentTime: TimeInterval
        @Binding var isPlaying: Bool
        weak var webView: WKWebView?

        init(currentTime: Binding<TimeInterval>, isPlaying: Binding<Bool>) {
            _currentTime = currentTime
            _isPlaying = isPlaying
        }

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            guard let body = message.body as? [String: Any] else { return }

            if message.name == "vimeoTime" {
                if let seconds = body["seconds"] as? Double {
                    DispatchQueue.main.async {
                        self.currentTime = seconds
                    }
                }
            } else if message.name == "vimeoState" {
                if let state = body["state"] as? String {
                    DispatchQueue.main.async {
                        self.isPlaying = (state == "playing")
                    }
                }
            }
        }

        /// 指定タイムコードへシーク
        func seek(to seconds: TimeInterval) {
            let js = "seekTo(\(seconds));"
            webView?.evaluateJavaScript(js, completionHandler: nil)
        }

        /// 再生
        func play() {
            webView?.evaluateJavaScript("playVideo();", completionHandler: nil)
        }

        /// 一時停止
        func pause() {
            webView?.evaluateJavaScript("pauseVideo();", completionHandler: nil)
        }
    }
}

// MARK: - シンプル埋め込みプレイヤー（編集後タブ等で使用、バインド不要版）
/// 再生位置のバインドが不要なシンプルなVimeo埋め込みプレイヤー
/// YouTube同様、直接URLRequestでVimeo embed URLを読み込む方式
struct VimeoEmbedPlayerView: UIViewRepresentable {
    let videoId: String
    /// 限定公開動画のプライバシーハッシュ（unlisted動画に必要）
    var privacyHash: String? = nil

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.scrollView.isScrollEnabled = false
        webView.backgroundColor = .black
        webView.isOpaque = false

        // Vimeo embed URLを直接読み込む（loadHTMLString + iframeだとbaseURL問題でブロックされる）
        // 限定公開動画はh=パラメータが必要
        let hashParam = privacyHash.map { "&h=\($0)" } ?? ""
        let embedURLString = "https://player.vimeo.com/video/\(videoId)?title=0&byline=0&portrait=0&color=1694F5&playsinline=1\(hashParam)"
        if let url = URL(string: embedURLString) {
            var request = URLRequest(url: url)
            request.setValue("https://video-director.app/", forHTTPHeaderField: "Referer")
            webView.load(request)
        }
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        // 静的表示のため更新不要
    }
}
