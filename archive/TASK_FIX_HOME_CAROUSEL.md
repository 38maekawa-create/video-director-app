# タスク指示書: ホームカルーセルのタップ修正 + ソート修正

<!-- authored: T1/副官A/AI開発10/2026-03-15 [なおとさんとの対話セッション中に作成] -->

## 目的
VideoDirectorAgent iOSアプリのホーム画面で、横スクロールカルーセル内のプロジェクトカードをタップして詳細画面に遷移できるようにする。加えて、撮影日順ソートのデータ不整合を修正する。

## 背景
Build 8〜17で計10回、SwiftUIのジェスチャーシステム内でのアプローチを試みたが全て失敗した。
- onTapGesture → 横ScrollViewがタップを吸収
- Button + .buttonStyle(.plain) → 同上
- NavigationLink(value:) → 同上
- .contentShape(Rectangle()) → 効果なし
- Button + NavigationPath → 同上
- fullScreenCover + onTapGesture → 同上
- Button + カスタムButtonStyle → 同上
- ScrollViewTouchFix (UIViewRepresentable) → 効果なし
- DragGesture(minimumDistance:0) + .simultaneousGesture → 横スクロール自体が壊れた（改悪）

**根本原因**: SwiftUIのScrollView(.horizontal)がScrollView(.vertical)内にネストされると、内部のタッチイベントがScrollViewのジェスチャー認識に消費され、子ビューに伝達されない。SwiftUIのジェスチャーシステム内での解決は困難。

## 全体工程における位置づけ
- このタスクが完了すると、ホーム画面からプロジェクト詳細への遷移が可能になり、アプリの主要導線が機能する
- レポートタブからの遷移は既に動作している（List内のNavigationLinkを使用）

## 修正内容

### 1. カルーセルのタップ修正

**推奨アプローチ**: SwiftUIのScrollView(.horizontal)を使わず、UIKit(UICollectionView or UIScrollView)でカルーセルを実装する。

具体的には:
- `UIViewRepresentable`でラッパーを作成
- 内部でUIScrollViewを使い、`delaysContentTouches = false` を設定
- 各カードはSwiftUIの`UIHostingConfiguration`または`UIHostingController`でレンダリング
- タップは UIKit側の `UITapGestureRecognizer` で処理
- タップ時に`selectedProject`を更新してSwiftUI側の`.fullScreenCover`で遷移

**対象ファイル**: `/Users/maekawanaoto/AI開発10/VideoDirectorAgent/VideoDirectorAgent/Views/ProjectListView.swift`

**現在の構造**:
```
NavigationStack
  ScrollView(.vertical)
    VStack
      heroSection (onTapGesture) ← ヒーローバナー、タップ可否未確認
      searchBar
      VStack
        carouselSection × 3 (最近のFB, 要対応, 全プロジェクト)
          ScrollView(.horizontal) ← ★ここが問題
            HStack
              ForEach { cardButton(project) } ← タップが効かない
  .fullScreenCover(item: $selectedProject) ← 遷移先
```

**注意事項**:
- 横スクロールは必ず維持すること（Build 17で壊れた）
- カード位置の上揃えを維持すること（.frame(height: 170, alignment: .top)）
- 職業テキスト(guestOccupation)の表示を維持すること

### 2. ソート修正（APIサーバー側）

**問題**: 2月28日大阪撮影の7名（コテさん、kosさん、メンイチさん、さといも・トーマスさん、ハオさん、けーさん、さくらさん、ゆりかさん）の`shoot_date`が全て`2026/01/01`になっている。titleには「2月28日 大阪」と記載されているため、正しくは`2026/02/28`であるべき。

**APIサーバーのデータを修正する必要がある。**

APIサーバーの場所: `http://100.110.206.6:8210`
APIエンドポイント: `GET /api/projects`

バックエンドのソースを確認し、以下のプロジェクトのshoot_dateを修正:
- コテさん → 2026/02/28
- kosさん → 2026/02/28
- メンイチさん → 2026/02/28
- さといも・トーマスさん → 2026/02/28
- ハオさん → 2026/02/28
- けーさん → shoot_dateを確認・修正
- さくらさん → shoot_dateを確認・修正
- ゆりかさん → shoot_dateを確認・修正

## 完了条件
1. ホームの全プロジェクトカルーセルで、カードをタップすると詳細画面が表示される
2. 横スクロールが正常に動作する
3. 職業テキストが正しく表示される
4. カードの位置が上揃えで統一されている
5. 撮影日が正しくソートされている（最新が左/上）
6. TestFlightにアップロードして実機確認

## 検証方法
- 実機（TestFlight）でホーム画面のカードをタップして反応するか確認
- 横スクロールが正常か確認
- ソート順が撮影日の新しい順か確認
- 全プロジェクト（29件）が表示されるか確認

## ビルド手順
```bash
cd /Users/maekawanaoto/AI開発10/VideoDirectorAgent
xcodebuild -scheme VideoDirectorAgent -sdk iphoneos -configuration Release -archivePath /tmp/VideoDirectorAgent.xcarchive archive
xcodebuild -exportArchive -archivePath /tmp/VideoDirectorAgent.xcarchive -exportOptionsPlist /tmp/ExportOptions.plist -exportPath /tmp/VideoDirectorAgent_export
```

## 過去の失敗アプローチ（これらは試さないこと）
1. SwiftUI onTapGesture
2. SwiftUI Button + .buttonStyle(.plain)
3. SwiftUI NavigationLink(value:)
4. .contentShape(Rectangle())
5. SwiftUI Button + NavigationPath
6. fullScreenCover + onTapGesture
7. Button + カスタムButtonStyle
8. ScrollViewTouchFix (UIViewRepresentable でdelaysContentTouches修正)
9. DragGesture(minimumDistance:0) + .simultaneousGesture
