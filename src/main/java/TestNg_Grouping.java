import org.apache.log4j.LogManager;
import org.apache.log4j.Logger;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.Assert;
import org.testng.Reporter;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

public class TestNg_Grouping {

  private   Logger Log = LogManager.getLogger(LogExample.class.getName());

  private   WebDriver driver;

    @Test
    public void a() throws InterruptedException {
//WebDriverManager.chromedriver().setup();



        //  DOMConfigurator.configure("log4j.xml");
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("chrome");
        driver = new ChromeDriver(options);
       // driver.get("https://demoqa.com/text-box/");
        driver.get("https://demoqa.com/");
        driver.manage().window().maximize();
        Log.info("Window is maximize here ");

        Reporter.log("Here is report text print here");



    }

    @Test(groups = { "group1" })
    public void b() {
        String testTitle = "Free QA Automation Tools For Everyone";
        String originalTitle = driver.getTitle();
        Assert.assertEquals(originalTitle, testTitle);


    }

    @Test(groups = { "group2" })
    public void c() {
     //   driver.findElement(By.xpath("//*[@id=\"sidebar\"]/aside[1]/ul/li[1]/a")).click();
        System.out.println("Home Page heading is displayed");
    }

@Test
@Parameters({"username","password"})
    //@Test

    public void userdetails(String username, String password)
    {
        System.out.println("Your username = " + username );
        System.out.println("Your Password = " + password );
    }


}
