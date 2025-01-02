import org.apache.log4j.LogManager;
import org.apache.log4j.Logger;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.firefox.FirefoxDriver;
import org.testng.Assert;
import org.testng.Reporter;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeTest;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

public class TestNgMultipleBrowser {

    private Logger Log = LogManager.getLogger(LogExample.class.getName());

    private WebDriver driver;

    @Parameters("browser")
    @BeforeTest
    public void browser(String browser) throws InterruptedException {
//WebDriverManager.chromedriver().setup();
//  DOMConfigurator.configure("log4j.xml");

        if(browser.equalsIgnoreCase("chrome")) {


            System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
            ChromeOptions options = new ChromeOptions();
            options.addArguments("chrome");
            driver = new ChromeDriver(options);
            // driver.get("https://demoqa.com/text-box/");
            Log.info("Chrome browser is launched ");

        } else if (browser.equalsIgnoreCase("firefox")) {

            driver = new FirefoxDriver();
            Log.info("Firefox browser is launched ");

        }
        else
            Log.info("No Browser Launched ");


        driver.get("https://demoqa.com/");
        driver.manage().window().maximize();
        Log.info("Window is maximize here ");

        Log.info("Here is report text print here");



    }

    @Test(priority=1)
    public void b() {
        String testTitle = "DEMOQA";
        String originalTitle = driver.getTitle();
        Assert.assertEquals(originalTitle, testTitle,"Title not found");
        Log.info("Page Title is ===" + originalTitle);


    }

    //@Test(groups = { "group2" })
    @Test(priority=2)
    public void c() {
        //   driver.findElement(By.xpath("//*[@id=\"sidebar\"]/aside[1]/ul/li[1]/a")).click();
        System.out.println("Home Page heading is displayed");

        driver.quit();
    }


}
