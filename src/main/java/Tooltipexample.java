import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.interactions.Actions;
import org.testng.annotations.Test;

public class Tooltipexample {

    @Test
    public void doubleclickexample() {
        System.setProperty("webdriver.chrome.driver", "D:\\Intellij\\chromedriver.exe");

        // Create a new instance of the Firefox driver
        WebDriver driver = new ChromeDriver();

        // Launch the URL
        driver.get("https://demoqa.com/tool-tips/");
        System.out.println("Tooltip web Page Displayed");

        //Maximise browser window
        driver.manage().window().maximize();

        Actions action =new Actions(driver);

        WebElement tool = driver.findElement(By.id("toolTipButton"));

        action.moveToElement(tool).perform();


      WebElement  toolTip = driver.findElement(By.cssSelector(".tooltiptext"));

        // To get the tool tip text and assert
        String toolTipText = toolTip.getText();
        System.out.println("toolTipText-->"+toolTipText);

        //Verification if tooltip text is matching expected value
        if(toolTipText.equalsIgnoreCase("We ask for your age only for statistical purposes.")){
            System.out.println("Pass* : Tooltip matching expected value");
        }else{
            System.out.println("Fail : Tooltip NOT matching expected value");
        }

        // Close the main window





    }

}