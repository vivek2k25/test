import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.Assert;
import org.testng.annotations.AfterTest;
import org.testng.annotations.Test;

public class ChromeHeadless {

    //   public class ChromeHeadless {
    WebDriver driver;

    @Test
    public void verifyTitlewithHeadless() throws InterruptedException {
//WebDriverManager.chromedriver().setup();

        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("chrome");
        options.setAcceptInsecureCerts(true);

        driver = new ChromeDriver(options);
        driver.get("https://www.browserstack.com/");
        System.out.println("Title is: " + driver.getTitle());
        Assert.assertEquals(driver.getTitle(), "Most Reliable App & Cross Browser Testing Platform | BrowserStack");


        //Now click on the search button

       WebElement searchbar = driver.findElement(By.xpath("//button[contains(@class,'bstack-mm-search-menu doc-search-menu dropdown-toggle doc-search-cta doc-search-menu-icon doc-menu-toggle hide-sm hide-xs')]"));

       //searchbar.getSize();
       System.out.println("Size of search bar is =====" + searchbar.getSize() );
       searchbar.click();

        System.out.println("Click on the search button");



        driver.findElement(By.xpath("//input[contains(@class,'ais-SearchBox-input')]")).sendKeys("selenium");

        driver.findElement(By.xpath("//input[contains(@class,'ais-SearchBox-input')]"));






        // Browser commands

/*


        String Title = driver.getTitle();
        System.out.println("Page title is == " + Title);

        // Storing Title length in the Int variable
        int titleLength = driver.getTitle().length();

        // Printing Title & Title length in the Console window
        System.out.println("Title of the page is : " + Title);
        System.out.println("Length of the title is : " + titleLength);

        String currentUrl = driver.getCurrentUrl();
        System.out.println("Page URL  is == " + currentUrl);

        String pgsource = driver.getPageSource();
        //System.out.println("Page Soruce  is == "+ pgsource);


        //  }

*/

   /*@Test

    public void browsercommands() {
*/
  /*      Thread.sleep(10000);

        driver.navigate().to("https://google.com");

        Thread.sleep(10000);
        System.out.println("Navigated to Google site ");
        Thread.sleep(10000);
        driver.navigate().back();
        System.out.println("Navigated tpo back");
        Thread.sleep(10000);

        driver.navigate().forward();
        System.out.println("Navigated tpo farwared");

        Thread.sleep(10000);
        driver.navigate().refresh();
        Thread.sleep(10000);
*/
    }
//    @AfterTest
    public void closeBrowser()
    {
        //Closing a browser
        driver.quit();
        System.out.println("Broser closed successfully");

    }



    }
