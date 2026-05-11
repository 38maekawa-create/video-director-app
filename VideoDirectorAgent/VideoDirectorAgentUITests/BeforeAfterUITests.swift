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
        XCTAssertTrue(openButton.isEnabled)

        openButton.tap()

        let title = app.staticTexts["ビフォーアフター"]
        let emptyState = app.staticTexts["ビフォーアフター素材が未連携です"]
        let screenOpened = title.waitForExistence(timeout: 20) || emptyState.waitForExistence(timeout: 20)
        XCTAssertTrue(screenOpened)
        XCTAssertEqual(app.state, .runningForeground)
    }
}
