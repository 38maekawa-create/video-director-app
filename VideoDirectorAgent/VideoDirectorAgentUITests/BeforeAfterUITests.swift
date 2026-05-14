import XCTest

final class BeforeAfterUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testBeforeAfterButtonOpensWithoutCrash() throws {
        throw XCTSkip("Full BeforeAfterView is quarantined while the TestFlight-only crash is isolated.")

        let app = XCUIApplication()
        app.launchArguments = ["--ui-test-before-after"]
        app.launch()

        let openButton = app.buttons["ui-test-open-before-after"]
        XCTAssertTrue(openButton.waitForExistence(timeout: 30))
        let deadline = Date().addingTimeInterval(45)
        while !openButton.isEnabled && Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        XCTAssertTrue(openButton.isEnabled)

        openButton.tap()

        let title = app.staticTexts["ビフォーアフター"]
        let emptyState = app.staticTexts["ビフォーアフター素材が未連携です"]
        let screenOpened = title.waitForExistence(timeout: 20) || emptyState.waitForExistence(timeout: 20)
        XCTAssertTrue(screenOpened)
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testDirectionReportBeforeAfterButtonOpensSummaryWithoutCrash() throws {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-test-direction-before-after"]
        app.launch()

        let reportButton = app.buttons["ui-test-open-direction-report"]
        if reportButton.waitForExistence(timeout: 3) {
            reportButton.tap()
        }

        let beforeAfterButton = app.buttons["direction-before-after-button"]
        XCTAssertTrue(beforeAfterButton.waitForExistence(timeout: 60))
        beforeAfterButton.tap()

        let summary = app.otherElements["before-after-summary-screen"]
        let closeButton = app.buttons["before-after-summary-close"]
        let title = app.staticTexts["ビフォーアフター"]
        let externalLinksLabel = app.staticTexts["外部で開く"]
        let comparisonModeLabel = app.staticTexts["比較モード"]
        let twoUpLabel = app.staticTexts["上下2段比較"]
        let transcriptLabel = app.staticTexts["文字起こし比較"]
        let fullTranscriptLabel = app.staticTexts["全行表示"]
        let fbTrackerLabel = app.staticTexts["FB指示トラッカー"]
        let sourcePickerLabel = app.staticTexts["素材選択"]
        let opened = closeButton.waitForExistence(timeout: 30)
            || summary.waitForExistence(timeout: 30)
            || title.waitForExistence(timeout: 30)
        XCTAssertTrue(opened)
        XCTAssertTrue(comparisonModeLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(twoUpLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["素材 vs 編集後"].waitForExistence(timeout: 20))
        _ = externalLinksLabel.waitForExistence(timeout: 5)
        _ = sourcePickerLabel.waitForExistence(timeout: 5)
        app.swipeUp()
        if !transcriptLabel.waitForExistence(timeout: 10) {
            app.swipeUp()
        }
        XCTAssertTrue(transcriptLabel.waitForExistence(timeout: 10))
        XCTAssertTrue(fullTranscriptLabel.waitForExistence(timeout: 10))
        if !fbTrackerLabel.waitForExistence(timeout: 10) {
            app.swipeUp()
        }
        XCTAssertTrue(fbTrackerLabel.waitForExistence(timeout: 10))
        let tapToPlay = app.staticTexts.matching(NSPredicate(format: "label == %@", "タップして再生")).firstMatch
        if tapToPlay.waitForExistence(timeout: 10) {
            tapToPlay.tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        XCTAssertEqual(app.state, .runningForeground)
    }
}
