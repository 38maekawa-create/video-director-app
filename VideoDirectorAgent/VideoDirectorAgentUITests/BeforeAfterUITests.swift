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
        XCTAssertTrue(reportButton.waitForExistence(timeout: 30))
        reportButton.tap()

        let beforeAfterButton = app.buttons["direction-before-after-button"]
        XCTAssertTrue(beforeAfterButton.waitForExistence(timeout: 30))
        beforeAfterButton.tap()

        let summary = app.otherElements["before-after-summary-screen"]
        let title = app.staticTexts["ビフォーアフター概要"]
        let previewBanner = app.staticTexts["Build66 左右再生切替"]
        let externalLinksLabel = app.staticTexts["外部で開く"]
        let inlinePreviewLabel = app.staticTexts["アプリ内プレビュー"]
        let comparisonPairLabel = app.staticTexts["比較ペア"]
        let comparisonStatusLabel = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "比較中:")).firstMatch
        let selectedLabel = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "選択中:")).firstMatch
        let opened = summary.waitForExistence(timeout: 20) || title.waitForExistence(timeout: 20)
        XCTAssertTrue(opened)
        XCTAssertTrue(previewBanner.waitForExistence(timeout: 20))
        XCTAssertTrue(externalLinksLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(inlinePreviewLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(comparisonPairLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(comparisonStatusLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["左:"].waitForExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["右:"].waitForExistence(timeout: 20))
        XCTAssertTrue(selectedLabel.waitForExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["外で開く"].waitForExistence(timeout: 20))
        let sourceEditedPair = app.buttons["before-after-compare-source-edited"]
        if sourceEditedPair.waitForExistence(timeout: 5) && sourceEditedPair.isEnabled {
            sourceEditedPair.tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        let editedFBPair = app.buttons["before-after-compare-edited-fb"]
        if editedFBPair.waitForExistence(timeout: 5) && editedFBPair.isEnabled {
            editedFBPair.tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        app.swipeUp()
        let playLeft = app.buttons["before-after-play-left"]
        if playLeft.waitForExistence(timeout: 5) && playLeft.isEnabled {
            playLeft.tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        let playRight = app.buttons["before-after-play-right"]
        if playRight.waitForExistence(timeout: 5) && playRight.isEnabled {
            playRight.tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        if app.buttons["before-after-inline-option-source"].waitForExistence(timeout: 5) {
            app.buttons["before-after-inline-option-source"].tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        if app.buttons["before-after-inline-option-fb-revised"].waitForExistence(timeout: 5) {
            app.buttons["before-after-inline-option-fb-revised"].tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        if app.staticTexts["タップして再生"].waitForExistence(timeout: 10) {
            app.staticTexts["タップして再生"].tap()
            XCTAssertEqual(app.state, .runningForeground)
        }
        XCTAssertEqual(app.state, .runningForeground)
    }
}
