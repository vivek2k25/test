import org.apache.log4j.LogManager;
import org.apache.log4j.Logger;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

public class TestNgPriority_group {

        // private static Logger Log = Logger.getLogger(LogExample.class.getName());
        Logger Log = LogManager.getLogger(LogExample.class.getName());

        WebDriver driver;

        @Test(priority=1)
        public void otherseleniumcommands() throws InterruptedException {
//WebDriverManager.chromedriver().setup();



            //  DOMConfigurator.configure("log4j.xml");
            System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
            ChromeOptions options = new ChromeOptions();
            options.addArguments("chrome");
            driver = new ChromeDriver(options);
            driver.get("https://demoqa.com/text-box/");
            driver.manage().window().maximize();
            Log.info("Window is maximize here ");


            JavascriptExecutor js = (JavascriptExecutor)driver;
            js.executeScript("return window.innerHeight;");

            js.executeScript("return window.innerWidth;");

        }

        @Test(priority=2)
        public void anothermethodfortest()
        {
            Log.info("class 2 executed here " + driver.getTitle());


        }

        @Test(priority=3)
        public void gettingtext()
        {
            WebElement ele = driver.findElement(By.className("text-center"));

            Log.info("Get the page center text " + ele.getText());

        }



    @Parameters({"vivek","Vivek@123"})
    @Test

    public void userdetails(String username, String pwd)
    {
        System.out.println("Your username = " + username );
        System.out.println("Your Password = " + pwd );
    }




}

