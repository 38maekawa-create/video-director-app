import XCTest

final class BeforeAfterUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testBeforeAfterButtonOpensWithoutCrash() throws {
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

    func testDirectionReportBeforeAfterButtonIsQuarantinedWithoutCrash() throws {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-test-direction-before-after"]
        app.launch()

        let reportButton = app.buttons["ui-test-open-direction-report"]
        XCTAssertTrue(reportButton.waitForExistence(timeout: 30))
        reportButton.tap()

        let beforeAfterButton = app.buttons["direction-before-after-button"]
        XCTAssertTrue(beforeAfterButton.waitForExistence(timeout: 30))
        beforeAfterButton.tap()

        let alert = app.alerts["ビフォーアフターを一時停止中"]
        XCTAssertTrue(alert.waitForExistence(timeout: 20))
        XCTAssertEqual(app.state, .runningForeground)
    }
}
