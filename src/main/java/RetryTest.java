import org.testng.Assert;
import org.testng.IRetryAnalyzer;
import org.testng.annotations.Test;

public class RetryTest {


    @Test(retryAnalyzer = IRetryAnalyzer.class)
    public void Test1()
    {
        Assert.assertEquals(false, true);
    }

    @Test
    public void Test2()
    {
        Assert.assertEquals(false, true);
    }
}

